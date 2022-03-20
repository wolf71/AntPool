'''
  Antpool Executor

  @ 2021/2              By Charles Lai

'''

__version__ = '0.12'
__author__ = 'Charles Lai'

import json, time, threading
import inspect, base64,pickle
import asyncio, concurrent.futures
from tornado.websocket import websocket_connect

# 通过这个类来进行 ws 连接，而后生成一个 Executor 对象
# 从concurrent.futures._base.Executor继承了__enter__() 和 __exit__()方法，这意味着可以用with
class AntPoolExecutor(concurrent.futures._base.Executor):
  '''
  ## AntPool.AntPoolExecutor compliant Python concurrent.futures.ProcessPoolExecutor
    - multi-thread using python:    concurrent.futures.ThreadPoolExecutor
    - multi-process using python:   concurrent.futures.ProcessPoolExecutor
    - multi-computer using AntPool: AntPool.AntPoolExecutor
  - Use the same method:
    - submit(fn, *args, **kwargs) executes fn(*args, **kwargs) and returns a Future object
      - result(timeout=None)  returns the return value of the call
      - add_done_callback(fn) add callback
    - map(func, *iterables, timeout=None, chunksize=1)
    - shutdown(wait=True)
  '''

  # 类变量, 用于存储 类消息接收 loop event
  loop = None

  # 负责异步发送 WebSocket 消息 
  async def wssent(self, info):
    await self.ws.write_message(info)

  # WebSocket 接收信息处理 （以独立线程运行，不会造成阻塞）
  def _wsRecv(self, srvurl):
    # 在独立线程启动循环
    def _start_thread_loop(loop):
      # 通过传入的 loop 参数，将当前线程的 事件循环 设置好，并且启动
      asyncio.set_event_loop(loop)
      loop.run_forever()

    # websocket 消息接收循环
    async def run(srvurl, loop):
      self.ws = await websocket_connect(srvurl)
      # 连接建立后，登陆客户端
      await self.ws.write_message(json.dumps({'c':'LOGIN','r':'1','s':'1','v':{'user':self.user,'pwd':self.pwd}}))
      # 获取返回结果
      info = await self.ws.read_message()
      rinfo = json.loads(info)
      if ('C' in rinfo) and ('s' in rinfo) and ('v' in rinfo) and rinfo['C'] == 'LOGIN':
          if 'cID' in rinfo['v']:
              self.cID = int(rinfo['v']['cID'])
              if self.cID <= 0:
                  raise
      # 有 执行标志 才循环
      while self.RecvLoop_flag:
        try:
          info = await self.ws.read_message()
        except:
          self.RecvLoop_flag = 0
          info = None
        # 初始化参数
        cmd,pstamp,v,ret,retval = '','','',1,None
        if info:
          try:
            info = json.loads(info)
            cmd,pstamp,v = info['C'],int(info['s']),info['v']
            # 任务执行完毕后的回报数据
            if cmd == 'JOB':
              # 等待结果任务计数器 - 1 
              self.execq_cnt -= 1
              # 获取结果
              ret = v['ret']
              # 如果返回正确，则解码；否则直接获取错误信息(因为错误信息未编码)
              # ret = 1，表示远端代码运行出现错误（例如被0除，语法错误等）
              if ret < 2:
                  retval = pickle.loads(base64.b64decode(v['retval'][2:]))
              else:
                  retval = v['retval']
              # 根据 pstamp 进行回调操作, 采用set_result()返回
              self._tasks[pstamp].set_result(retval)
            # 收到指令接收OK消息
            # elif cmd == 'RJOB':
            #   self.rok = True
          except:
            pass
        else:           # 数据接收错误，则退出循环
          self.RecvLoop_flag = 0
      
    # 以 独立线程 运行 一个独立的 Loop event ，负责接收所有回包数据
    if not AntPoolExecutor.loop:
      AntPoolExecutor.loop = asyncio.new_event_loop()
      t = threading.Thread(target=_start_thread_loop, args=(AntPoolExecutor.loop,))
      t.daemon = True
      t.start()
    # 启动 websocket 接收循环
    asyncio.run_coroutine_threadsafe(run(srvurl, AntPoolExecutor.loop), AntPoolExecutor.loop)

  def __init__(self, srvurl, max_workers=8, rtype = 0, user='user',pwd='pwd'):
    '''
      srvurl: antpool server, etc: ws://127.0.0.1:8086
      max_workers: set the max_workers (default is 8)
      rtype: running model(default is 0) 0-global/local environment is reset before the run; 1-After the run, g/l environment is reset; 2-g/l continuing with the last environment
    '''
    # 与任务服务器建立 WebSocket 连接，并且进行认证
    self.cID = 0
    self.tID = 0
    self.user = user
    self.pwd = pwd
    self.RecvLoop_flag = 1
    self.execq_cnt = 0
    self.Max_execq = max_workers
    self.rtype = rtype
    # 用于保存正在执行的任务id与Future对象 {id:future对象}
    self._tasks={}
    self.ws = None
    # 启动Websocket Receive 线程
    self._wsRecv(srvurl+'/ws')
    # 等待完成连接
    while 1:
      if self.cID >0:
        break
      else:
        time.sleep(0.05)
    
  def shutdown(self, wait=True):
    # 如果需要等待任务完成后退出，则等待 execq_cnt 变为 0
    if wait:
        while self.execq_cnt > 0:
          time.sleep(0.05)
    # 设置 ws 接收循环退出标志
    self.RecvLoop_flag = 0
    # 关闭 websocket 
    self.ws.close()

  # Submits a callable to be executed with the given arguments. Returns: A Future representing the given call.
  def submit(self, fn, *args, **kwargs):
    if self.cID > 0 and self.RecvLoop_flag:
        # 获取代码，需要规避前面的无效内容
        # 将函数 代码 + 调用参数 获取，并且进行编码，构造成适合 JSON 发送的字符串
        # 因为需要用到 pickle 进行变量序列化，因此在这里进行 import 
        rcode = inspect.getsource(fn)
        rcode = 'import pickle,base64\n' + rcode[rcode.find('def '):]
        # 调用 参数 序列化，并且转换为字符串 (这样就可以兼容参数的各种类型，包括 int,float,str,list,dict,bytes等)
        # 如果直接对二进制数据进行 str 操作，size会比 str(base64.b64encode()) 大
        rcode += '\nr1t_arg = pickle.loads(base64.b64decode("' + str(base64.b64encode(pickle.dumps(args)))[2:] + '"))'
        rcode += '\nr1t_kwarg = pickle.loads(base64.b64decode("' + str(base64.b64encode(pickle.dumps(kwargs)))[2:] + '"))'
        # 构建调用函数的语句，并且设定返回变量
        rcode += '\nr1t_va1=' + fn.__name__ + '(*r1t_arg,**r1t_kwarg)'
        # 设置调用指针
        self.tID += 1
        self.execq_cnt += 1
        # 如果有太多等待任务，则等待任务完成才继续
        while self.execq_cnt > self.Max_execq:
            time.sleep(0.05)
        # 通过线程安全的模式, 将要发送的数据通过 websocket 给服务器发送调用指令，指令将通过回调返回结果
        asyncio.run_coroutine_threadsafe( self.wssent(json.dumps({'c':'JOB','r':'1','s':self.tID,'v':{'type':self.rtype,'code':rcode}})), AntPoolExecutor.loop )
        # 将要运行的函数、参数记录下来，发送到远端；而后等待返回结果，将序号和 f 绑定
        f = concurrent.futures._base.Future()
        self._tasks[self.tID] = f
        return f
    else:
        if self.cID > 0:
            raise RuntimeError('Cannot schedule new futures after shutdown')
        else:
          raise RuntimeError('Cannot connect to Server')

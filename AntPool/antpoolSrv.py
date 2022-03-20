#-*- encoding:utf-8 -*-  

'''
    AntPool Server

    @ 2015/8      init version for python2          By Charles Lai
    @ 2021/2      change to python3 support         By Charles Lai

'''

__version__ = '0.12'
__author__ = 'Charles Lai'

import tornado.gen, tornado.ioloop
import tornado.web, tornado.websocket, tornado.httpserver
import time, json, os, logging, sys

# 没有资源时候，等待多久返回错误信息 （单位：S)
Res_Waittime = 6

# WebSocket 心跳检测间隔时间 (秒, 0-表示停用心跳检测)
# 心跳时间过短，会导致在执行长时间任务时，资源端没有回应
gWebsocket_ht = 60

# Websocket 默认消息大小 (每次发送/接收的最大值,单位是 Bytes)
websocket_max_message_size = 32 * 1024 * 1024

# 系统日志文件前缀（日志为: logname_log.txt ，错误输出为： logname_err.txt)
logname = 'aSrv'

# 定义全局变量
aRes = None                   # 资源对象
aCli = None                   # 任务客户端对象

# 日志文件
#
# 当前运行程序目录
AppDir = os.path.split(os.path.realpath(__file__))[0] + '/'
# 如果需要显示在屏幕上，则在命令后加上 v 参数
syslogf = AppDir + logname
ssl_enable = False
tronado_debug = False

# 设置日志对象
# 需要使用的地方，使用：logging.debug('This is debug message %s, id:=%s','aaa','bbb')
# 日志级别：CRITICAL > ERROR > WARNING > INFO > DEBUG > NOTSET
# 
logfile = syslogf+'_log.txt' 
logfilelev = logging.ERROR
logscrlev = logging.WARNING
logfmt = '%(asctime)s %(filename)s:%(lineno)s - %(message)s' 
# logdfmt = '%d/%m/%Y %H:%M:%S'     # add datefmt=logdfmt to basicConfig
logfmode = 'a'     # w 表示每次重新覆盖， a 表示在后面新增
logtofile = True   # 将错误信息输出到文件
# 如果有/v参数，则添加一个屏幕输出 Handle
for i in sys.argv:
    if i == '/v':                   # 设置调试信息输出
        lconsole = logging.StreamHandler()
        # 这里定义的级别，必须依赖根定义的，如果根定义的较高，则这里就算定义较低也没用
        lconsole.setLevel(logscrlev)
        logging.getLogger('').addHandler(lconsole)
        logtofile = False
        # 启动输入调试信息，则默认打开 Tronada debug 模式，会自动重新加载 web 目录下的变化内容
        tronado_debug = True
    elif i == '/s':                 # 开启 SSL
        ssl_enable = True
# 对 logging 对象进行配置
logging.basicConfig(level=logfilelev,format=logfmt,filename=logfile,filemode=logfmode)
# 将所有错误重定位到错误日志文件，而不是在屏幕上输出
if logtofile:
    errfsock = open(syslogf+'_err.txt', 'a')
    sys.stderr = errfsock

# 获取本机IP地址
def get_localip():
    import socket
    gAdd = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    gAdd.connect(('www.bing.com', 80))
    return gAdd.getsockname()[0]

#
# 客户端 调度类
#
# clist = {'cID':{'ID':self.cnt, 'IP':cIP, 'cval':cval, 'cb':cb, 'rcnt':0, 'rfcnt':0}, ...}
#   cID: 客户端唯一ID, IP: 客户端IP, cval: 客户端当下传送过来的负载内容,   cb: 客户端 Websocket 连接,  rcnt:运行次数,  rfcnt:资源失败次数
# 
class aClient:
    def __init__(self):
        self.cnt = 0
        self.clist = {}

    # 客户端登陆
    def login(self,cval,cIP,cb):
        self.cnt += 1
        # 可以通过 cval['user'],cval['pwd']获取用户名、密码来验证
        self.clist[self.cnt]={'IP':cIP, 'cval':cval, 'cb':cb, 'rcnt':0, 'rfcnt':0}
        # 返回对应的 client ID (如果失败，则返回0)
        return self.cnt

    # 客户端注销
    def remove(self,cID):
        # 删除对应用户
        try:
            del self.clist[cID]
        except:
            pass

    # 判断对应用户是否在线
    def check(self,cID):
        if cID in self.clist:
            return 1
        else:
            return 0

    # 列出所有当前在线用户
    def show(self):
      ostr = '## Number of working clients: %d\n'%len(self.clist)
      for i in self.clist:
          ostr += '- [%d] IP: %s Tasks run: %d  failures: %d \n' % (i,self.clist[i]['cb'].IP,self.clist[i]['rcnt'],self.clist[i]['rfcnt'])
      return ostr

#
# 资源 管理/调度 类 
#
#   rlist = {'rID':{'flag':0,'cID':0,'cb':cb,'jcb':'','callID':0,'cnt':0,'pong':1,'rinfo':{资源配置信息},'stime':0,'ttime':0,'rsize':0,'ssize':0}, ...}
#     rID: 资源端唯一ID      flag: 是否空闲可以执行任务 0-空闲/1-正忙；  cb：对应资源端 websocket 指针  rinfo: 资源配置参数（OS/RAM/Speed...)
#     最近一次执行的客户端信息： cID: 对应的任务客户端ID; jcb: 对应任务客户端 websocket 指针; callID: 对应任务客户端的调用唯一ID
#     cnt：该资源累计执行次数； pong: 如果收到对应 pong 则为1；（该标志会被定时执行的 ping/pong 检测重置和判断）
#     stime: 资源累计CPU运行代码时长   ttime: 资源累计 接受/发送指令 + cpu 运行总时长   rsize: 资源累计接收 指令包 大小   ssize：资源累计发送 返回参数 大小
#
class aResource:
    def __init__(self):
        self.rcnt = 0
        self.rlist = {}

    # 设置收到PONG标志
    def pong(self,rID):
        self.rlist[rID]['pong'] = 1

    # 资源客户端登陆
    def reg(self,rinfo,cb):
        self.rcnt += 1
        # 资源端OS类型、内存、计算性能存储在 rinfo 字典中；cb.IP 是资源端 IP地址
        # 记录资源信息（并且可以拒绝不合格资源注册等）
        self.rlist[self.rcnt] = {'flag':0,'cID':0,'cb':cb,'jcb':'','callID':0,'cnt':0,'pong':1,'rinfo':rinfo['info'],'stime':0,'ttime':0,'rsize':0,'ssize':0}
        # 返回对象对应的 Resource ID，如果失败，则返回0
        return self.rcnt

    # 资源端离线退出
    def remove(self,rID):
        # 如果该资源正在执行任务，并且还未完成，则需要给任务客户端发送失败信息
        if self.rlist[rID]['flag'] == 1:
            self.rlist[rID]['jcb']._main_cb('JOB', self.rlist[rID]['callID'], {'ret':99,'retval':'Run error, resource client error!'})
        # 删除资源
        try:
            del self.rlist[rID]
        except:
            pass

    # 异步模式实现资源选择(不阻塞主进程)
    async def getResource(self,cID,pstamp,jcb):
        n, exec_flag, time_cnt = 0, 1, Res_Waittime/0.05
        # 在设定时间内，获取空闲的资源
        while exec_flag and time_cnt > 0:
            time_cnt -= 1
            # 将资源按照 cnt 排序，确保资源调用次数均衡 ['cnt']
            # r_list = sorted(self.rlist.items(),key=lambda d:d[1]['cnt'])
            # 按照 CPU 性能排序, CPU性能越高的优先使用 ['rinfo']['cpu']
            r_list = sorted(self.rlist.items(),key=lambda d:d[1]['rinfo']['cpu'], reverse=True)
            for i in r_list:
                # 确认该资源空闲
                if i[1]['flag'] == 0:
                    n = i[0]
                    self.rlist[n]['flag'] = 1
                    self.rlist[n]['cID'] = cID
                    self.rlist[n]['jcb'] = jcb
                    self.rlist[n]['callID'] = pstamp
                    self.rlist[n]['cnt'] += 1
                    # 设置退出循环标志
                    exec_flag = 0
                    break
            # 没有资源，则等待一段时间 (非阻塞延时)
            await tornado.gen.sleep(0.05)
        # 如果有资源，则返回资源ID；否则返回0表示资源不足 (并且累加客户端使用计数器)
        if n > 0:
            aCli.clist[cID]['rcnt'] += 1
        else:
            aCli.clist[cID]['rfcnt'] += 1
        # 返回资源ID
        return n

    # 列出所有当前在线资源端信息
    def show(self):
      ostr = '## Number of resource clients: %d\n'%len(self.rlist)
      for i in self.rlist:
          rinfo = self.rlist[i]['rinfo']
          ostr += '- [%d] IP: %s   (Runs: %d, CPU times: %.1fs, Total times: %.1fs, Net Recv: %.3fM, Sent: %.3fM ) ||  OS: %s,RAM: %s(%s free) CPU rank: %s \n' % (i,self.rlist[i]['cb'].IP, self.rlist[i]['cnt'], self.rlist[i]['stime'],self.rlist[i]['ttime'],self.rlist[i]['rsize']/1024/1024,self.rlist[i]['ssize']/1024/1024,rinfo['sys'], rinfo['tmem'], rinfo['fmem'],rinfo['cpu'])
      return ostr

#
# 基于 websocket 长连接
#
class WebSocketHandler(tornado.websocket.WebSocketHandler): 
  
    def __init__(self, application, request, **kwargs):
        tornado.websocket.WebSocketHandler.__init__(self, application, request, **kwargs)

    # 需要这个返回 True，否则就出现 403 错误
    def check_origin(self, origin):  
        return True  

    # 连接后需要马上进行认证，如果没有认证，应该马上断开连接（避免恶意连接）
    def open(self):  
        self.cID, self.rID = 0, 0
        # 获取客户端 IP 地址
        self.IP = self.request.remote_ip or self.request.headers.get("X-Real-IP") or self.request.headers.get("X-Forwarded-For")

    @tornado.gen.coroutine
    def on_message(self, message):  
        # 心跳检测 Ping/Pong
        if message == 'PONG' and self.rID > 0:
            # 设置收到 PONG 标志
            aRes.pong(self.rID)
        # 正常信息处理
        else:
            # 获取JSON格式指令信息，而后解析，如果符合要求，则按照指令调用相关业务逻辑
            try:
                i_len = len(message)
                cinfo = json.loads(message)
                # 避免传入的数据非 JSON 而引发后续解析出错
                if type(cinfo) != dict:
                    raise RuntimeError('WebSock_on_message Format error.')
            except:
                logging.error('WebSock_on_message input parameter JSON parsing error!')
            else:
                # 根据参数进行业务逻辑分配
                # cmd: 指令类型, pver: 指令版本号, pstamp: 指令序列号, cval: 负载内容
                if ('c' in cinfo) and ('r' in cinfo) and ('s' in cinfo) and ('v' in cinfo):
                    cmd,pver,pstamp,cval = cinfo['c'],cinfo['r'],cinfo['s'],cinfo['v']
                    # 参数合规审核
                    if isinstance(cmd,str) and (isinstance(cval,list) or isinstance(cval,dict)):
                        # 对于命令符，限制在8字符，以避免恶意破坏!!!
                        cmd,pver = cmd[:8],pver[:3]
                        # 资源客户端注册
                        if cmd == 'REG':
                            # 如果资源未注册，则进行注册，否则直接返回资源ID
                            if self.rID == 0: 
                                self.rID = aRes.reg(cval,self)
                            # 根据注册情况，返回结果
                            if self.rID > 0:
                                self._main_cb(cmd,pstamp,{'ret':0,'rID':self.rID})
                            else:
                                # 资源端注册失败
                                self._main_cb(cmd,pstamp,{'ret':1,'rID':0})
                        # 任务客户端登录
                        elif cmd == 'LOGIN':
                            # 用户未登录过，则进行登录处理
                            if self.cID == 0:
                                self.cID = aCli.login(cval,self.IP,self)
                            # 根据登录情况返回结果
                            if self.cID > 0:
                                self._main_cb(cmd,pstamp,{'ret':0,'cID':self.cID})
                            else:
                                # 登录失败
                                self._main_cb(cmd,pstamp,{'ret':1,'cID':0})
                        # 资源客户端退出
                        elif cmd == 'REMOVE':
                            self.close
                        # 任务客户端提交任务
                        elif cmd == 'JOB':
                            if self.cID > 0:
                                # 使用同步方式获取资源，并且向空闲资源发送任务
                                rID = yield aRes.getResource(self.cID,pstamp,self)
                                # 如果有资源可用，发送任务到 资源端 执行 
                                # 指令串中，pstamp保存了资源ID，以便资源运行完成后回包处理
                                if rID > 0:
                                    aRes.rlist[rID]['cb']._main_cb('RUN',str(rID),{'callID':pstamp,'type':cval['type'],'code':cval['code'],'btime':time.time(),'rlen':i_len})
                                else:
                                    # 没有资源可用
                                    self._main_cb('JOB', pstamp, {'ret':40,'retval':'Insufficient resources!'})
                            else:
                                self._main_cb(cmd,pstamp,{'ret':30,'err':'Not certified!'})
                        # 资源客户端完成任务后，回送结果
                        elif cmd == 'ROK':
                            rID = int(pstamp)
                            # 若客户端在线，才发回结果
                            if aCli.check(aRes.rlist[rID]['cID']):
                               try:
                                   # 累加资源端 CPU 运行时长、 网络往返+CPU 累计时长、 网络数据包收发量
                                   aRes.rlist[rID]['stime'] += float(cval['stime'])
                                   aRes.rlist[rID]['ttime'] += round(time.time() - float(cval['btime']),3)
                                   aRes.rlist[rID]['rsize'] += int(cval['rlen'])        # 资源端接收 指令包 数据量
                                   aRes.rlist[rID]['ssize'] += i_len                    # 资源端发送 返回包 数据量
                                   # 发送 确认信息给 资源端
                                   self._main_cb(cmd, aRes.rlist[rID]['callID'], {'ret':0})
                                   # 将结果发送给 任务客户端
                                   aRes.rlist[rID]['jcb']._main_cb('JOB', aRes.rlist[rID]['callID'], {'ret':cval['errcode'],'retval':cval['ret']})
                               except:
                                   pass
                            # 标记资源为空闲（需要等上面结果发送回客户端才标记空闲，否则如发送时间较长，而先设置空闲会导致问题）
                            aRes.rlist[rID]['flag'] = 0
                        else:
                            # 参数错误，返回错误信息
                            self._main_cb(cmd,pstamp,{'ret':20,'err':'Call parameters do not match!'})
                    else:
                        logging.error('WebSock_on_message parameter error (cmd,val)!')
                else:
                    logging.error('WebSock_on_message Wrong input parameter, missing parameter!')

    def on_close(self):  
        # 如果 cID>0 需要注销任务客户， rID>0 需要注销资源
        if self.cID >0: aCli.remove(self.cID)
        if self.rID >0: aRes.remove(self.rID)

    # 将内容以 JSON 的格式发送到 客户端/资源端
    # cmd - 调用的命令, pstamp - 时间戳, cval - 返回的结果内容集（list or dict)
    def _main_cb(self,cmd,pstamp,cval):
        try:
            self.write_message(json.dumps({'C':cmd,'s':str(pstamp),'v':cval}))
        except:
            pass

#
# 提供 Web 管理后台服务
#
class WebHandler(tornado.web.RequestHandler):
    def get(self):
      # 获取 url 参数
    #   a = self.get_query_argument("a",default='  None  ',strip=True)
    #   clientIP = self.request.remote_ip or self.request.headers.get("X-Real-IP") or self.request.headers.get("X-Forwarded-For")
      # 返回页面
      rhtml = '<html><center><h2>AntPool Server Monitoring</h2></center>'
      rhtml += aRes.show().replace('\n','<br>') + '<br>' + aCli.show().replace('\n','<br>')
      rhtml += '</html>'
      self.write(rhtml)

class Application(tornado.web.Application):
    def __init__(self):  
        handlers = [  
            # Web 管理服务
            (r"/antadmin", WebHandler),
            # 标准 WebSocket
            (r'/ws', WebSocketHandler)
        ]
        # websocket_max_message_size 设置 websocket 一次最大接受数据 （默认10M bytes）
        settings = {'debug':tronado_debug, 'gzip':True,'websocket_max_message_size':websocket_max_message_size}
        tornado.web.Application.__init__(self, handlers, **settings)

        # 设置异步 ping/pong 检测 (借助 Tornado 的定时任务功能)
        if gWebsocket_ht > 0:
            tornado.ioloop.PeriodicCallback(self.pingpong, gWebsocket_ht * 1000).start()
            
    # 定期进行 ping/pong 监测，判断资源客户端是否离线
    def pingpong(self):
        # 检测过期未回复资源
        for i in aRes.rlist:
            # 未收到 PONG ，且不属于正在运行任务的，则进行清除
            if (aRes.rlist[i]['pong'] == 0) and (aRes.rlist[i]['flag'] == 0):
                aRes.rlist[i]['cb'].close()
            else:
            # 否则向该资源发送 Ping 包，并清除收到 Pong 标志
                try:
                    aRes.rlist[i]['cb'].write_message('PING')
                    # 清除收到PONG标志
                    aRes.rlist[i]['pong'] = 0
                except:
                    pass

def main():
    global aRes, aCli 

    # 初始化 资源/任务客户端 对象
    aRes = aResource()
    aCli = aClient()

    # 判断端口参数 (默认为 8080，参数为第一个： xxx.py 8101 /v)
    if len(sys.argv) > 1 and sys.argv[1] and sys.argv[1].isdigit():
        sport = int(sys.argv[1])
    else:
        sport = 8086

    # 启动 Tornado 主服务线程
    ws_app = Application()
    # 根据SSL开关确定是否启用SSL功能（默认启用）
    if ssl_enable:
        server = tornado.httpserver.HTTPServer(ws_app,ssl_options = {"certfile":AppDir+"cacert.csr","keyfile":AppDir+"privkey.key"})
    else:
        server = tornado.httpserver.HTTPServer(ws_app)
    server.listen(sport)
    logging.warning('### aSrv start @ %s:%s SSL=%s',get_localip(),sport,ssl_enable)
    try:
        tornado.ioloop.IOLoop.instance().start()
    except:
        logging.warning('### aSrv Stop ...')
        server.stop()

if __name__ == '__main__':
    main()


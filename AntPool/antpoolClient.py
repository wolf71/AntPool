'''

    AntPool Resource Client (Tornado Version)
    
    @ 2021/2              By Charles Lai

'''

__version__ = '0.12'
__author__ = 'Charles Lai'

from tornado.ioloop import IOLoop
from tornado import gen
from tornado.websocket import websocket_connect
import json, time, pickle, base64, sys

#
# 返回：设备操作系统类型、总内存、剩余内存
#
def getMEM():
    import os,sys
    # 获取内存值
    stype = sys.platform
    tmem,fmem = 0,0
    try:
        if stype == 'darwin':
            meminfo = os.popen("top -l 1 -s 0 | grep PhysMem").readlines()[0].split()
            tmem,fmem = meminfo[1],meminfo[5]
        elif stype == 'win32':
            import psutil
            mem = psutil.virtual_memory()
            tmem,fmem = int(mem.total/1024/1024), int(mem.free/1024/1024)
        elif stype.find('linux')>-1:
            meminfo = os.popen("free -m").readlines()
            tmem,fmem = meminfo[1].split()[1],meminfo[1].split()[3]
    except:
        pass
    return stype,tmem,fmem

#
# 计算 CPU 性能 (输出值为 速率参数，越大速度越快)
# 
def getCPU():
    import time
    bt, tmp = time.time(), 0.0
    for i in range(3000000):
        tmp = tmp + (i/3721.523 * 3.12345678)/6.23
    tspent =  int((1/(time.time()-bt))*1000)
    return tspent
    

#
# 客户端类
#   
class rClient(object):
    def __init__(self, url, timeout=10):
        self.url = url
        self.timeout = timeout
        self.runflag = 1
        self.ioloop = IOLoop.current()
        self.ws = None
        self.cID = 0        
        self.rcInfo = {}
        self.rcInfo['sys'], self.rcInfo['tmem'], self.rcInfo['fmem'] = getMEM()
        self.rcInfo['cpu'] = getCPU()
        # 启动信息接收主循环
        self.run()
        # # 启动 ioloop
        try:
          self.ioloop.start()
        except KeyboardInterrupt:
            if self.cID > 0:
              # 如果中断，则主动注销资源
              self.ws.write_message(json.dumps({'c':'REMOVE','r':'1','s':'1','v':{}}))
              self.ws.close()
            # 停止整个循环
            self.runflag = 0
            self.ioloop.stop()
        
    @gen.coroutine
    def connect(self):
        self.cID = 0
        print('Try Connect to Server : ', self.url)
        try:
            self.ws = yield websocket_connect(self.url+'/ws')
        except:
            pass
        else:
            # 连接建立后，资源注册
            yield self.ws.write_message(json.dumps({'c':'REG','r':'1','s':'1','v':{'info':self.rcInfo}}))
            # 获取返回结果
            info = yield self.ws.read_message()
            rinfo = json.loads(info)
            if ('C' in rinfo) and ('s' in rinfo) and ('v' in rinfo) and rinfo['C'] == 'REG':
              if 'rID' in rinfo['v']:
                self.cID = int(rinfo['v']['rID'])
                print('Connect OK,rID=',self.cID)
        # 返回资源ID
        return self.cID
            
    @gen.coroutine
    def run(self):
        g,l = {},{}
        while self.runflag:
            # 如果没有建立连接(或连接断开)，则建立连接(建立不成功, 延时2s继续重试)
            if not self.ws:
                while 1:
                    cID = yield self.connect()
                    if cID > 0:
                        break
                    else:
                        time.sleep(2)
            # 如果连接已经建立，则获取数据
            info = yield self.ws.read_message()
            # 如果连接被中断，则关闭连接
            if info is None: 
                self.ws = None
            # 处理 PING/PONG 包 （回应服务器的 PING 包）
            if info == 'PING':
                self.ws.write_message('PONG')
            else:
                try:
                    rinfo = json.loads(info)
                except:
                    rinfo = {}
                # 解析数据 & 显示数据
                if ('C' in rinfo) and ('s' in rinfo) and ('v' in rinfo):
                    cmd,pstamp,cval = rinfo['C'],rinfo['s'],rinfo['v']
                    # 执行命令
                    if cmd == 'RUN':
                        # Base64解码
                        # code = base64.b64decode(cval['code'])
                        bt = time.time()
                        code = cval['code']
                        # type 参数 = 0-表示在运行前，重置 g/l 环境； 1-运行后，重置 g/l 环境； 2-运行前后都不清除环境，继续上次环境
                        if cval['type'] == 0:
                            g, l = {}, {}
                        try:
                            exec(code, g, l)
                            errcode, retval = 0, l['r1t_va1']
                        except KeyboardInterrupt:
                            # 如果中断，则主动注销资源
                            self.ws.write_message(json.dumps({'c':'REMOVE','r':'1','s':'1','v':{}}))
                            self.ws.close()
                            raise
                        except:
                            # 运行出现错误, 获取错误信息返回
                            einfo = sys.exc_info()
                            errcode, retval = 1, str(einfo[1])
                        # 根据 type 参数，确定是否清除环境变量
                        if cval['type'] == 1:
                            g, l = {}, {}
                        # 返回结果（需要对结果进行序列化、base64处理)
                        retval = str( base64.b64encode( pickle.dumps(retval) ) )
                        self.ws.write_message(json.dumps({'c':'ROK','r':'1','s':pstamp,'v':{'callID':cval['callID'],'errcode':errcode,'ret':retval,'stime':round(time.time()-bt,3),'btime':cval['btime'],'rlen':cval['rlen']}}))
                    # 返回结果成功获取
                    elif cmd == 'ROK':
                        pass
                else:
                    pass

def main():
    # 获取服务器参数
    if len(sys.argv)>1:
        srvurl =  sys.argv[1]
    else:
        # 默认参数
        srvurl = 'ws://127.0.0.1:8086'
    # 启动资源客户端
    rClient(srvurl, 5)

if __name__ == "__main__":
    main()    
# AntPool - Python Minimalist multi-computer distributed computing framework

## What
- AntPool provides a server and resource client that makes it easy and fast to set up a multi-computer distributed environment.
- AntPool provides a development library consistent with Python's native concurrent.futures.Executor asynchronous library, allowing you to quickly deploy your code to run in the multi-computer distributed environment.

## Why 
- In some application scenarios, we want programs to run on multiple machines in parallel to gain **performance, network access** improvements;
	- **Computational Performance Boost**: For complex computation and analysis in Python, multi-threaded Python can't boost on multi-core CPUs(limit by GIL), so Python introduced the concurrent.futures.ProcessPoolExecutor, Multi-process development is easy to implement; but when higher performance is needed, a multi-computer distributed environment quickly allows you to change just a few lines of code and take performance to new heights.
	- **Network Capability Improvement**: Crawling data on the Internet, analyzing and extracting it, is often limited by the traffic of the crawled server. Therefore, it is necessary to deploy the program to multiple machines with different network addresses for crawling, which is tedious and error-prone to do manually, but a multi-machine distributed environment can quickly solve such problems.
- **Everyone Can Using** Instead of requiring complex configurations, specialized equipment, and relearning how to develop, AntPool is available to everyone.
	- Any single device can be used as a server or resource client or both. These include PC/Mac/Linux computers, and even devices like your iPhone/iPad/Android that can run Python.
	- You can use all your devices at home to help you improve your computing performance, or you can ask your colleagues at work to contribute some of their CPU cores to help you achieve complex computations.
	- All computing resources are connected to a server-driven cluster network by running a resource client, which can be joined and quit flexibly.
	- No need to learn new concepts, as you only need to understand Python's native concurrent.futures.Executor, as the AntPool classes are same.
- **Mobile Device Support** iPad is a great tool, and there are already many great apps that run Python and iPython Notebook, but due to iOS security restrictions, many libraries can't be installed, Python also don't support multi-processing. With AntPool, you can call a multi-machine cluster directly on the iPad and run features on the cluster that are not available on the iPad or get more performance.
	- iPad Python Apps
		- Pythonista (requires [stash](https://github.com/ywangd/stash) , for pip support)
		- Pyto
		- CodeApp
	- iPad iPython Notebook/Jupyter Apps
		- Juno
		- Carnets

## How
- Runtime requirements: 
	- Python 3.5 or above
- Quick Start:
	- **pip3 install antpool**
	- Standalone deployment server and resource client
		- Run in a terminal environment: **antpoolsrv /v**
		- Open a new terminal and run: **antpoolclient ws://127.0.0.1:8086**
		- If you need to access more resource clients to improve cluster performance, you can do so on other machines:
			- **pip3 install antpool**
			- **antpoolclient ws://server IP:8086**
		- Each antpoolclient client running on the same machine will use one CPU core, so if you want to exploit the performance of the whole machine, you can run multiple clients (e.g. for a 4-core CPU machine, you can run 4 clients)
	- Run the demo program
		- **python3 demo1.py**  (demo1.py on github.com/wolf71/AntPool/demo)
	- Structure diagram
	![AntPool Struct](https://github.com/wolf71/AntPool/blob/master/antpool_s.jpg?raw=true)

## !!! Security Tip !!!
- The resource client is execution of the submitted modules, so the device running the resource client will be vulnerable to attacks by users with bad intentions, the system does not perform security checks on the executed modules, so it is recommended that the user running the resource client needs to verify that the user is trustworthy;
- For the sake of simplicity, the entire system currently does not use user/password authentication mechanisms (interfaces are reserved in the code); therefore, it is recommended that the server be deployed on the public network with security in mind;


## User Manual

### 1. AntPool Server
- **antpoolSrv port /s /v**
	- port: Websocket port, default is 8086
	- /s open websocket SSL support
	- /v debug mode, will show debug info on screen, otherwise all message write on log file.
		- logfile: aSrv_log.txt
		- error: aSrv_err.txt
	- A multi-computer distributed environment only needs to run one server program.
- **Web monitoring**
	- open browser, goto http://xxx:port/antadmin  View server information (current resource client, task client status)
- SSL config
	- Generate SSL keys (using Tornado to support SSL is much less powerful than using Nginx, so recommend using Nginx SSL)
		- openssl genrsa -out privkey.key 2048
		- openssl req -new -x509 -key privkey.key -out cacert.csr -days 1095
		- and then copy this two file to antpoolSrv.py same directory.

### 2. AntPool Resource Client
- **antpoolClient server_addr**
	- server_addr: the AntPool Server websocket address, just like ws://192.168.3.3:8086 , or wss://srv1.mycorp.com:8086 (for SSL)
	- default is ws://127.0.0.1:8086
- You can run Resource Client on the same machine with Server or run multi Resource Client on same machine. (resource client count <= CPUs)
- You can run Resource client on multiple machines connect to the server in order to scale the performance.

### 3. Develop your application with AntPool.AntPoolExecutor
- Please read the documentation for Python concurrent.futures **first**
	- https://docs.python.org/3/library/concurrent.futures.html
- AntPool.AntPoolExecutor compliant Python concurrent.futures
	- multi-thread using python:    concurrent.futures.ThreadPoolExecutor
	- multi-process using python:   concurrent.futures.ProcessPoolExecutor
	- multi-computer using AntPool: AntPool.AntPoolExecutor
- AntPool.AntPoolExecutor
	- **AntPoolExecutor(srvurl, max_workers=8, rtype = 0, user='user',pwd='pwd')**
  	- srvurl: antpool server, etc: ws://127.0.0.1:8086
    - max_workers: set the max_workers (default is 8)
    - rtype: running model(default is 0) 0-global/local environment is reset before the run; 1-After the run, g/l environment is reset; 2-g/l continuing with the last environment
		- user/pwd: Reserved, not used in current version
	- **AntPoolExecutor.submit**(fn, *args, **kwargs)
		- sent fn(*args, **kwargs) to the cluster server parallel execution and returns a Future object, has the following methods
			- result(timeout=None)  returns the return value of the call (!! blocking until get result or timeout)
			- add_done_callback(fn) add callback
	- **AntPoolExecutor.map(func, *iterables, timeout=None, chunksize=1)**
	- **AntPoolExecutor.shutdown(wait=True)**
		- frees resources by executing the join() method for each thread or process; you can avoid using this method by using the with statement.

### 4. Show me your code
```python
# import AntPoolExecutor
from AntPool import AntPoolExecutor

# setup antpool Server address 
srv = 'ws://127.0.0.1:8086'

#
# your parallel function 
#
def test(n):
  # import python module here 
  from random import random
  # your jobs here
  cnt = 0
  for i in range(1, n+1):
    cnt += i
  # return result
  return cnt

# parallel calc 20 times
r_n = 20 

# using AntPoolExecutor.map execute parallel
with AntPoolExecutor(srv) as executor:
  # parallel send tasks and waitting all task result
  r = executor.map( test, [20000000 for i in range(r_n)] )
  # sum result (the r is a list)
  print('### %d times, total = %d'%(r_n, sum(r)))
```

## Background and History
- Based on the requirement of fast crawling network data, which needs to be processed by multiple machines/multiple IPs in parallel, the initial version was completed in October 2015, using for parallel data crawling/processing. (Initial release based on Python2 / Tornado / callback mode)
- 2021/2 Python3 support (dropping python2 support) , and deprecated callback mode, changed it to be consistent with python native concurrent.futures interface; and added web status monitoring function.
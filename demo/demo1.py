'''
   # AntPool Simply Demo1
   - using AntPool parallel calc 1+2+3+....+n
   - please config: srv, n , s 
   - set p_flag = 1, Show execution process; or p_flag = 0 disable

'''

import time
from AntPool import AntPoolExecutor

#
# please config here 
#

# antpool Server address 
srv = 'ws://127.0.0.1:8086'
# Calc 1+2+....n 
n = 100000000
# split s tasks
s = 4
# show
p_flag = 1


# for callback using global
cb_sum = 0

# Test function Calc b + (b+1) + (b+2) + .... + e
def test(c, b, e):
  cnt = 0
  for i in range(b, e + 1):
    cnt += i
  return c, cnt

# callback function
def cb(f):
  global cb_sum
  # r is a list [c,cnt], because test return c, cnt
  r = f.result()
  cb_sum += r[1]
  if p_flag: print('# %d Callback, return=%d'%r)

# get time 
bt = time.time()

# Generate tasks
step = int(n/s)
b = 0
t = []
for i in range(s):
  t.append( (i+1, b+1, b+step) )
  b += step
# if n/s not int, so need append last task
if b < n: t.append( (i+2, b+1, n))


print('### Method 1: using with, will auto shutdown')
bt = time.time()
with AntPoolExecutor(srv) as executor:
  r_sum = 0
  jobs = []
  # sent all tasks to AntPool Server
  for i in t:
    r = jobs.append( executor.submit(test, i[0], i[1], i[2]) )
  # Get all task result
  for i in jobs:
    c, r = i.result() 
    r_sum += r
    if p_flag: print('# Task %d , Result: %d'%(c, r))
  print('### Total time: %.2fs, Result: 1+2+3+...+%d = %d'%(time.time()-bt, n, r_sum))


print('\n### Method 2: using callback mode')
bt = time.time()
executor = AntPoolExecutor(srv)
# sent all tasks to AntPool Server and set callback
for i in t:
  executor.submit(test, i[0], i[1], i[2]).add_done_callback(cb)
# you need call shutdown
executor.shutdown()
print('### Total time: %.2fs, Result: 1+2+3+...+%d = %d'%(time.time()-bt, n, cb_sum))


print('\n### Method 3: using map auto sum')
bt = time.time()
with AntPoolExecutor(srv) as executor:
  ret = executor.map(test, [i[0] for i in t], [i[1] for i in t], [i[2] for i in t])
print('### Total time: %.2fs, Result: 1+2+3+...+%d = %d'%(time.time()-bt, n, sum([i[1] for i in ret])))

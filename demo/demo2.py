'''
   # AntPool Simply Demo2
    - This demo will test and comparison Python ThreadPoolExecutor, ProcessPoolExecutor, AntPoolExecutor
    - This test will using PIL to Generate complex graphics, and then compress to jpeg.
    - The jpeg data will sent back from all Resource Client to your application.
    
    - please config: srv, t_n

'''

import time
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
from AntPool import AntPoolExecutor

#
# please config here 
#

# antpool Server address 
srv = 'ws://127.0.0.1:8086'

# tasks
t_n = 10


#
# your function
#
def test(x, y):
  from random import random
  from io import BytesIO
  from PIL import Image, ImageDraw

  # define your class
  class myImage:
    '''
      Generate graphs for testing
      x,y = image size
    '''
    def __init__(self, x=1024, y=768):
      self.x = x
      self.y = y
      self.img = Image.new('RGB', (x, y), 'white')
      self.draw =ImageDraw.Draw(self.img)

    # Draw n random rectangle 
    def drawRect(self, n):
      for i in range(n):
        self.draw.rectangle( (int(random() * self.x/2), int(random() * self.y/2), int(random() * self.x/2), int(random() * self.y/2)) , 'blue', 'red')

    # Draw logistic map
    def drawlogistic(self, n=6000):
      d = []
      r, dr, y = 2.5, 0.1, 0.33
      for i in range(n):
        if r > 3.5: dr = 0.01	
        if i % 100 == 0: r += dr
        y = r * y * (1 - y)
        # append to points
        d.append( (int(self.x * i/n), int(self.y * y)) )
      # plot the point on image
      self.draw.point(d,'black')

    # get image 
    def gene(self):
      self.drawRect(20000)
      self.drawlogistic(6000)

    # convert to jpeg, and return jpeg size and jpeg data
    def tojpeg(self):
      with BytesIO() as output:
        self.img.save(output, format='jpeg')
        oimg = output.getvalue()
      return len(oimg), oimg
  #
  # your function here
  #
  img = myImage(x, y)
  img.gene()
  return img.tojpeg()


#
# Demo2 Main 
#
if __name__ == '__main__':

  print('## 1. Using Python ThreadPoolExecutor')
  bt = time.time()
  with ThreadPoolExecutor() as executor:
    ret = executor.map(test, [2048 for i in range(t_n)], [1600 for i in range(t_n)])
  # Get the result (from Future object to result)
  ret = [ i for i in ret]    
  print( '- Times: %.2f, total images size: %dKBytes'%(time.time()-bt, sum([i[0]/1024 for i in ret])) )

  print('\n## 2. Using Python ProcessPoolExecutor')
  bt = time.time()
  with ProcessPoolExecutor() as executor:
    ret = executor.map(test, [2048 for i in range(t_n)], [1600 for i in range(t_n)])
  # Get the result (from Future object to result)
  ret = [ i for i in ret]    
  print( '- Times: %.2f, total images size: %dKBytes'%(time.time()-bt, sum([i[0]/1024 for i in ret])) )

  print('\n## 3. Using AntPoolExecutor')
  bt = time.time()
  with AntPoolExecutor(srv) as executor:
    ret = executor.map(test, [2048 for i in range(t_n)], [1600 for i in range(t_n)])
  # Get the result (from Future object to result)
  ret = [ i for i in ret]
  print( '- Times: %.2f, total images size: %dKBytes'%(time.time()-bt, sum([i[0]/1024 for i in ret]))) 
  
  # last, select one image to Show it 
  # from PIL import Image
  # from io import BytesIO
  # Image.open(BytesIO(ret[0][1])).show()
 

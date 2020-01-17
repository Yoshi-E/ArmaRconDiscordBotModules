import sys
from subprocess import PIPE, Popen
from threading  import Thread


sys.exit("Use bot.py instead")

try:
    from queue import Queue, Empty
except ImportError:
    from Queue import Queue, Empty  # python 2.x

ON_POSIX = 'posix' in sys.builtin_module_names

def enqueue_output(out, queue):
    for line in iter(out.readline, b''):
        queue.put(line)
    out.close()

p = Popen(['python', 'bot.py'], stdout=PIPE, bufsize=1, close_fds=ON_POSIX)
q = Queue()
t = Thread(target=enqueue_output, args=(p.stdout, q))
t.daemon = True # thread dies with the program
t.start()

# ... do other things here

while True:
    # read line without blocking
    try:  
        #line = q.get_nowait() # or q.get(timeout=.1)
        line = q.get(timeout=.1)
    except Empty:
        pass #print('no output yet')
    else:
        print(line)
        print("yyay")
    
# From: https://gist.github.com/3492507
# Used to test the code.

from tornado.gen import engine, Runner, Task
from tornado.ioloop import IOLoop
from functools import wraps
import time

def init(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        engine(fn)(*args, **kwargs)
        IOLoop.instance().start()
    return wrapper

def halt():
    IOLoop.instance().stop()

def delay(seconds):
    return Task(IOLoop.instance().add_timeout, time.time()+seconds)
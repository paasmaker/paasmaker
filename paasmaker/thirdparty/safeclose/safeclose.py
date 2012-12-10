""" Copyright 2011 Andrei Savu 

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License. """

""" An easy way to ensure that programs will exit in safe fashion """

from signal import signal as setsignal
from signal import getsignal, SIGTERM, SIGINT

from contextlib import contextmanager

_exit_request = False
_handlers = []

def setup(onexit = None):
  """ Replace the default signal handlers with a new one """
  global _handlers

  if not _handlers:
    _handlers = [getsignal(SIGTERM), getsignal(SIGINT)]

  def _new_handler(*args):
    global _exit_request
    _exit_request = True

    if onexit is not None and callable(onexit):
      onexit()

  setsignal(SIGTERM, _new_handler)
  setsignal(SIGINT, _new_handler)

def restore():
  """ Restore signal handlers """
  global _handlers, _exit_request

  if _handlers:
    setsignal(SIGTERM, _handlers[0])
    setsignal(SIGINT, _handlers[1])

    _handlers = []
    _exit_request = False

def exit():
  """ Did we got an exit request? """
  return _exit_request

@contextmanager
def section(onexit = None):
  setup(onexit)
  yield 
  restore()
 


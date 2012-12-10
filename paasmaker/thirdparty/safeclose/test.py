#!/usr/bin/env python

from __future__ import with_statement

import os, sys
import signal
import time

import safeclose

def main():
  pid = os.fork()
  return child_main() if not pid else parent_main(pid)

def child_main():
  with safeclose.section():
    while not safeclose.exit():
      time.sleep(0.1)
  return 2

def parent_main(pid):
  time.sleep(1)
  os.kill(pid, signal.SIGTERM)

  pid, code = os.wait()
  assert code >> 8 == 2

  return 0

if __name__ == '__main__':
  if not os.fork():
    sys.exit(main())

  else:
    pid, status = os.wait()
    print "Testing safe close on SIGTERM ... ",
    assert status >> 8 == 0
    print '[ OK ]'

    print "Testing safe close on CTRL-C ..." 
    flag = False
    try:
      def onexit(): print 'Got exit request.'

      with safeclose.section(onexit):
        print "Press CTRL-C to exit."
        while not safeclose.exit():
          time.sleep(0.3)

      flag = True
    except KeyboardInterrupt:
      assert False # this should not happen

    assert flag is True
    print "[ OK ]"

    print "Done."

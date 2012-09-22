# From: https://gist.github.com/3492507
# Used to test the code.

import signal, sys
from   util import *

iterations = int(sys.argv[1])
itertime   = float(sys.argv[2])
killtime   = float(sys.argv[3])

@engine
def sigterm(*args):
    print >>sys.stderr, "got signal"
    yield delay(killtime)
    halt()

signal.signal(signal.SIGTERM, sigterm)
signal.signal(signal.SIGINT, sigterm)

@init
def main():
    for x in range(iterations):
        sys.stdout.write('-')
        yield delay(itertime)

    halt()

main()
#!/usr/bin/env python

# From http://docs.python.org/2/library/simplehttpserver.html
import os
import SimpleHTTPServer
import SocketServer

PORT = 8000

# Read in the port from the environment, if present.
if 'PM_PORT' in os.environ:
    PORT = int(os.environ['PM_PORT'])

Handler = SimpleHTTPServer.SimpleHTTPRequestHandler

httpd = SocketServer.TCPServer(("", PORT), Handler)

print "Listening for requests at http://localhost:%d" % PORT
httpd.serve_forever()
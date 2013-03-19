#!/usr/bin/env python
# Based on the following examples:
# http://docs.python.org/2/library/simplehttpserver.html
# http://www.acmesystems.it/python_httpserver

import os
import SocketServer
import BaseHTTPServer

PORT = 8000

class PaasmakerHandler(BaseHTTPServer.BaseHTTPRequestHandler):
	def do_GET(self):
		self.send_response(200)
		self.send_header('Content-type','text/html')
		self.end_headers()
		self.wfile.write("Hello, World!")

httpd = SocketServer.TCPServer(("", PORT), PaasmakerHandler)

print "Listening for requests at http://localhost:%d" % PORT
httpd.serve_forever()
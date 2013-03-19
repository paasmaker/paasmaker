#!/usr/bin/env python
# Based on the following examples:
# http://docs.python.org/2/library/simplehttpserver.html
# http://www.acmesystems.it/python_httpserver

import os
import glob
import json
import SocketServer
import BaseHTTPServer

PORT = 8000

# Read in the port from the environment, if present.
if 'PM_PORT' in os.environ:
        PORT = int(os.environ['PM_PORT'])

def format_environment_variable(variable_name):
	contents = None
	if variable_name in os.environ:
		contents = json.loads(os.environ[variable_name])

	response = 'Contents of %s:\n' % variable_name
	if contents is not None:
		response += json.dumps(contents, indent=4, sort_keys=True)
		response += '\n'
	else:
		response += '- No contents, variable not set.\n'

	return response

class PaasmakerHandler(BaseHTTPServer.BaseHTTPRequestHandler):
	def do_GET(self):
		self.send_response(200)
		self.send_header('Content-type','text/html')
		self.end_headers()
		response = '<pre>'
		response += 'My working directory: %s\n' % os.getcwd()
		response += 'Files in my working directory:\n'
		for filename in glob.glob('*'):
			response += '* %s\n' % filename
		response += format_environment_variable('PM_SERVICES')
		response += format_environment_variable('PM_METADATA')
		response += '</pre>'
		self.wfile.write(response)

httpd = SocketServer.TCPServer(("", PORT), PaasmakerHandler)

print "Listening for requests at http://localhost:%d" % PORT
httpd.serve_forever()
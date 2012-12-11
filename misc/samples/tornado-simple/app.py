#!/usr/bin/env python

import os
import json

# From http://www.tornadoweb.org/documentation/overview.html, with a few mods.
import tornado.ioloop
import tornado.web
from tornado.options import define, options

define("port", type=int, default=8888, help="The port to listen on.")

class MainHandler(tornado.web.RequestHandler):
	def get(self):
		self.write("Hello, world")

class EnvironHandler(tornado.web.RequestHandler):
	def get(self):
		result = '<pre>\n'
		for key, value in os.environ.iteritems():
			result += tornado.escape.xhtml_escape(key) + ' = '
			if len(value) > 0 and value[0] == '{':
				# We're assuming this is JSON... so decode and print it.
				decoded = json.loads(value)
				result += tornado.escape.xhtml_escape(json.dumps(decoded, sort_keys=True, indent=4))
			else:
				result += tornado.escape.xhtml_escape(value)
			result += "\n"
		result += '</pre>'

		self.write(result)

application = tornado.web.Application([
	(r"/", MainHandler),
	(r"/environ", EnvironHandler),
])

tornado.options.parse_command_line()

if __name__ == "__main__":
	print "Listening on 0.0.0.0:%d" % options.port
	application.listen(options.port)
	tornado.ioloop.IOLoop.instance().start()
#!/usr/bin/env python

# From http://www.tornadoweb.org/documentation/overview.html, with a few mods.
import tornado.ioloop
import tornado.web
from tornado.options import define, options

define("port", type=int, default=8888, help="The port to listen on.")

class MainHandler(tornado.web.RequestHandler):
	def get(self):
		self.write("Hello, world")

application = tornado.web.Application([
	(r"/", MainHandler),
])

tornado.options.parse_command_line()

if __name__ == "__main__":
	print "Listening on 0.0.0.0:%d" % options.port
	application.listen(options.port)
	tornado.ioloop.IOLoop.instance().start()
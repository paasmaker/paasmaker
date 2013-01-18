#!/usr/bin/env python

import os
import json

# From http://www.tornadoweb.org/documentation/overview.html, with a few mods.
import tornado.ioloop
import tornado.web
from tornado.options import define, options
from sphinx.websupport import WebSupport

support = WebSupport(
	datadir=os.path.abspath('documentation/websupport/data'),
	search='xapian'
)

print os.path.abspath('websupport')

define("port", type=int, default=8888, help="The port to listen on.")
define("debug", type=int, default=0, help="Use debug mode.")

class MainHandler(tornado.web.RequestHandler):
	def get(self):
		document = 'index'
		if self.request.uri != '/':
			document = self.request.uri[1:]

		contents = support.get_document(document)

		self.write(contents)

settings = {}
settings['debug'] = (options.debug == 1)
settings['xheaders'] = True
if not settings['debug']:
	# Turn on GZIP encoding, when not in debug mode.
	settings['gzip'] = True

application = tornado.web.Application([
	(r"/.*", MainHandler)
], **settings)

tornado.options.parse_command_line()

if __name__ == "__main__":
	print "Listening on http://0.0.0.0:%d" % options.port
	application.listen(options.port)
	tornado.ioloop.IOLoop.instance().start()
#!/usr/bin/env python

import tornado.ioloop
import tornado.web

import paasmaker

configuration = dict(configuration=None)
routes = []
routes.extend(paasmaker.controller.example.Example.get_routes(configuration))

application = tornado.web.Application(routes)

if __name__ == "__main__":
	application.listen(8888)
	tornado.ioloop.IOLoop.instance().start()

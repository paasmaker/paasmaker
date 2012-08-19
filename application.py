#!/usr/bin/env python

# External library imports.
import tornado.ioloop
import tornado.web

# Internal imports.
import paasmaker

# Logging setup.
# TODO: Allow this to be controlled by command line / configuration.
import logging
logging.basicConfig(format='%(asctime)s %(levelname)s %(message)s', level=logging.DEBUG)

# Load configuration
configuration = paasmaker.configuration.Configuration()
configuration.dump()

# Configure our application and routes.
route_extras = dict(configuration=configuration)
routes = []
routes.extend(paasmaker.controller.example.Example.get_routes(route_extras))

# Set up the application object.
application = tornado.web.Application(routes)

# Commence the application.
if __name__ == "__main__":
	application.listen(configuration.get_raw()['global']['http_port'])
	tornado.ioloop.IOLoop.instance().start()

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
logging.info("Loading configuration...")
configuration = paasmaker.configuration.Configuration()
configuration.dump()

# Configure our application and routes.
logging.info("Building routes.")
route_extras = dict(configuration=configuration)
routes = []
routes.extend(paasmaker.controller.example.Example.get_routes(route_extras))

# Set up the application object.
logging.info("Setting up the application.")
application = tornado.web.Application(routes)

# Commence the application.
if __name__ == "__main__":
	application.listen(configuration.get_flat('everywhere.http_port'))
	logging.info("Listening on port %d", configuration.get_flat('everywhere.http_port'))
	tornado.ioloop.IOLoop.instance().start()

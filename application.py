#!/usr/bin/env python

# External library imports.
import tornado.ioloop
import tornado.web
import tornado.options

# Internal imports.
import paasmaker

# Logging setup.
# TODO: Allow this to be controlled by command line / configuration.
import logging
logging.basicConfig(format='%(asctime)s %(levelname)s %(message)s', level=logging.INFO)

# Parse command line options.
tornado.options.parse_command_line()

# Load configuration
logging.info("Loading configuration...")
configuration = paasmaker.configuration.Configuration()
configuration.load_from_file(['../paasmaker.yml', '/etc/paasmaker/paasmaker.yml'])

# Reset the log level.
logging.info("Resetting server log level to %s.", configuration['server_log_level'])
logger = logging.getLogger()
logger.setLevel(getattr(logging, configuration['server_log_level']))
configuration.dump()

# Initialise the system.
# Set up the job logger.
paasmaker.util.joblogging.JobLoggerAdapter.setup_joblogger(configuration)

# Configure our application and routes.
logging.info("Building routes.")
route_extras = dict(configuration=configuration)
routes = []
#routes.extend(paasmaker.controller.example.ExampleController.get_routes(route_extras))
#routes.extend(paasmaker.controller.example.ExampleFailController.get_routes(route_extras))
routes.extend(paasmaker.controller.example.ExampleWebsocketHandler.get_routes(route_extras))
routes.extend(paasmaker.controller.information.InformationController.get_routes(route_extras))
routes.extend(paasmaker.controller.index.IndexController.get_routes(route_extras))

# Set up the application object.
logging.info("Setting up the application.")
application_settings = configuration.get_torando_configuration()
#print str(application_settings)
application = tornado.web.Application(routes, **application_settings)

# Commence the application.
if __name__ == "__main__":
	# Set up the application...
	application.listen(configuration['http_port'])
	logging.info("Listening on port %d", configuration['http_port'])
	# And start listening.
	tornado.ioloop.IOLoop.instance().start()

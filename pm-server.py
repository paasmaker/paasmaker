#!/usr/bin/env python

# External library imports.
import tornado.ioloop
import tornado.web
import tornado.options

# Internal imports.
import paasmaker

# Logging setup.
import logging
logging.basicConfig(format='%(asctime)s %(levelname)s %(message)s', level=logging.INFO)

# Parse command line options.
tornado.options.parse_command_line()

# Load configuration
logging.info("Loading configuration...")
configuration = paasmaker.common.configuration.Configuration()
configuration.load_from_file(['../paasmaker.yml', '/etc/paasmaker/paasmaker.yml'])

# Reset the log level.
logging.info("Resetting server log level to %s.", configuration['server_log_level'])
logger = logging.getLogger()
logger.setLevel(getattr(logging, configuration['server_log_level']))
configuration.dump()

# Initialise the system.
logging.info("Initialising system.")
route_extras = dict(configuration=configuration)
routes = []

# Set up the job logger.
paasmaker.util.joblogging.JobLoggerAdapter.setup_joblogger(configuration)
configuration.setup_job_watcher()

if configuration.is_pacemaker():
	# Pacemaker setup.
	# Connect to the database.
	logging.info("Database connection and table creation...")
	configuration.setup_database()

	logging.info("Setting up pacemaker routes...")
	routes.extend(paasmaker.pacemaker.controller.index.IndexController.get_routes(route_extras))
	routes.extend(paasmaker.pacemaker.controller.login.LoginController.get_routes(route_extras))
	routes.extend(paasmaker.pacemaker.controller.login.LogoutController.get_routes(route_extras))
	routes.extend(paasmaker.pacemaker.controller.user.UserEditController.get_routes(route_extras))
	routes.extend(paasmaker.pacemaker.controller.user.UserListController.get_routes(route_extras))
	routes.extend(paasmaker.pacemaker.controller.profile.ProfileController.get_routes(route_extras))
	routes.extend(paasmaker.pacemaker.controller.profile.ProfileResetAPIKeyController.get_routes(route_extras))
	routes.extend(paasmaker.pacemaker.controller.workspace.WorkspaceEditController.get_routes(route_extras))
	routes.extend(paasmaker.pacemaker.controller.workspace.WorkspaceListController.get_routes(route_extras))
	routes.extend(paasmaker.pacemaker.controller.role.RoleEditController.get_routes(route_extras))
	routes.extend(paasmaker.pacemaker.controller.role.RoleListController.get_routes(route_extras))
	routes.extend(paasmaker.pacemaker.controller.role.RoleAllocationListController.get_routes(route_extras))
	routes.extend(paasmaker.pacemaker.controller.role.RoleAllocationAssignController.get_routes(route_extras))
	routes.extend(paasmaker.pacemaker.controller.role.RoleAllocationUnAssignController.get_routes(route_extras))

	routes.extend(paasmaker.pacemaker.controller.application.ApplicationListController.get_routes(route_extras))
	routes.extend(paasmaker.pacemaker.controller.application.ApplicationNewController.get_routes(route_extras))
	routes.extend(paasmaker.pacemaker.controller.application.ApplicationController.get_routes(route_extras))
	routes.extend(paasmaker.pacemaker.controller.job.JobController.get_routes(route_extras))
	routes.extend(paasmaker.pacemaker.controller.job.JobStreamHandler.get_routes(route_extras))
	routes.extend(paasmaker.common.controller.log.LogStreamHandler.get_routes(route_extras))
	routes.extend(paasmaker.pacemaker.controller.version.VersionController.get_routes(route_extras))
	routes.extend(paasmaker.pacemaker.controller.version.VersionInstancesController.get_routes(route_extras))

	routes.extend(paasmaker.pacemaker.controller.version.VersionRegisterController.get_routes(route_extras))
	routes.extend(paasmaker.pacemaker.controller.version.VersionStartupController.get_routes(route_extras))
	routes.extend(paasmaker.pacemaker.controller.version.VersionShutdownController.get_routes(route_extras))
	routes.extend(paasmaker.pacemaker.controller.version.VersionDeRegisterController.get_routes(route_extras))

	routes.extend(paasmaker.pacemaker.controller.node.NodeRegisterController.get_routes(route_extras))
	routes.extend(paasmaker.pacemaker.controller.node.NodeListController.get_routes(route_extras))
	routes.extend(paasmaker.pacemaker.controller.node.NodeDetailController.get_routes(route_extras))

	# TODO: This might be disabled by the configuration.
	routes.extend(paasmaker.pacemaker.controller.upload.UploadController.get_routes(route_extras))

if configuration.is_heart():
	# Heart setup.
	pass

if configuration.is_router():
	# Router setup.
	# Connect to redis.
	pass

logging.info("Setting up common routes...")
routes.extend(paasmaker.common.controller.example.ExampleWebsocketHandler.get_routes(route_extras))
routes.extend(paasmaker.common.controller.information.InformationController.get_routes(route_extras))

# Set up the application object.
logging.info("Setting up the application.")
application_settings = configuration.get_tornado_configuration()
#print str(application_settings)
application = tornado.web.Application(routes, **application_settings)

def on_registration_complete(response):
	if not response.success or len(response.errors) > 0:
		logging.error("Unable to register with the master node.")
		for error in response.errors:
			logging.error(error)
		# TODO: Do we now quit? Or retry in a little bit?
	else:
		logging.info("Successfully registered or updated with master.")

def on_completed_startup():
	# Start listening for HTTP requests, as everything is ready.
	logging.info("Listening on port %d", configuration['http_port'])
	application.listen(configuration['http_port'])

	# Register the node with the server.
	if configuration.get_node_uuid():
		request = paasmaker.common.api.NodeUpdateAPIRequest(configuration)
		request.send(on_registration_complete)
	else:
		request = paasmaker.common.api.NodeRegisterAPIRequest(configuration)
		request.send(on_registration_complete)

def on_intermediary_started(message):
	logger.debug(message)
	on_intermediary_started.required -= 1
	# See if everything is ready.
	if on_intermediary_started.required == 0:
		on_completed_startup()
	else:
		logger.debug("Still waiting on %d other things for startup.", on_intermediary_started.required)

on_intermediary_started.required = 0

def on_intermediary_failed(message, exception):
	logger.error(message)
	logger.error(exception)
	logger.critical("Aborting startup due to failure.")
	tornado.ioloop.IOLoop.instance().stop()

def on_ioloop_started():
	logger.debug("IO loop running. Launching other connections.")

	# Job manager
	# TODO: Only need one count if the message exchange is not required.
	on_intermediary_started.required += 2
	configuration.startup_job_manager(on_intermediary_started, on_intermediary_failed)

	# Message exchange.
	configuration.setup_message_exchange(on_intermediary_started, on_intermediary_failed)

	logger.debug("Launched all startup jobs.")

# Commence the application.
if __name__ == "__main__":
	# Add a callback to get started once the IO loop is up and running.
	tornado.ioloop.IOLoop.instance().add_callback(on_ioloop_started)

	# Start up the IO loop.
	tornado.ioloop.IOLoop.instance().start()
	logging.info("Exiting.")

#!/usr/bin/env python

# External library imports.
import tornado.ioloop
import tornado.options

# Internal imports.
import paasmaker

# Logging setup.
import logging
logging.basicConfig(format='%(asctime)s %(levelname)s %(message)s', level=logging.INFO)

# Parse command line options.
other_options = tornado.options.parse_command_line()

# Load configuration
logging.info("Loading configuration...")
configuration = paasmaker.common.configuration.Configuration()
configuration.load_from_file(['../paasmaker.yml', '/etc/paasmaker/paasmaker.yml'])

# Reset the log level.
logging.info("Resetting command log level to %s.", configuration['server_log_level'])
logger = logging.getLogger()
logger.setLevel(getattr(logging, configuration['server_log_level']))

# Initialise the system.
logging.debug("Initialising system.")

# TODO: Rewrite the argument handling. Completely!

# Various commands that we can run.
def user(params):
	# TODO: Don't assume we have the right number of arguments.
	method = params[0]
	if method == 'create':
		login = params[1]
		name = params[2]
		email = params[3]
		password = params[4]

		request = paasmaker.common.api.user.UserCreateAPIRequest(configuration)
		request.set_user_params(name, login, email, True)
		request.set_user_password(password)
		request.send(generic_api_response)

def info(params):
	pass

def help(descriptions):
	for k, v in descriptions.iteritems():
		logging.info("%s: %s", k, v)
	exit()

HELP = {}
HELP['user'] = "Create and edit users."
HELP['info'] = "Get information."
HELP['help'] = "Get help."

# Lifecycle callbacks.
def on_start():
	logging.debug("Starting...")
	if len(other_options) == 0:
		logging.info("No command provided. Try 'help'.")
		exit()
	elif other_options[0] == 'user':
		user(other_options[1:])
	elif other_options[0] == 'info':
		info(other_options)
	else:
		help(HELP)

def generic_api_response(response):
	if response.success:
		logging.info("Successfully executed request.")
	else:
		logging.error("Request failed.")
		for error in response.errors:
			logging.error(error)
	exit()

def exit():
	tornado.ioloop.IOLoop.instance().stop()

# Commence the application.
if __name__ == "__main__":
	# Start the loop.
	try:
		tornado.ioloop.IOLoop.instance().add_callback(on_start)
		tornado.ioloop.IOLoop.instance().start()
		logging.debug("Exiting.")
	except Exception, ex:
		# Catch all, to catch things thrown in the callbacks.
		logging.error(ex)
		tornado.ioloop.IOLoop.instance().stop()

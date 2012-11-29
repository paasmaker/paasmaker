#!/usr/bin/env python

# External library imports.
import tornado.ioloop
import argparse

import sys
import json

# Internal imports.
import paasmaker

# Logging setup.
import logging
logging.basicConfig(format='%(asctime)s %(levelname)s %(message)s', level=logging.INFO)

# TODO: Write tests for all the actions in this file. Integration tests might cover this off
# though? But need to make sure we have appropriate coverage.

# TODO: When an error occurs, exit.

class RootAction(object):
	def options(self, parser):
		# Define your options here.
		pass

	def process(self, args):
		self.exit()

	def describe(self):
		raise NotImplementedError("Not implemented.")

	def prettyprint(self, data):
		print json.dumps(data, indent=4, sort_keys=True)

	def exit(self, code):
		tornado.ioloop.IOLoop.instance().stop()
		sys.exit(code)

	def point_and_auth(self, args, apirequest):
		scheme = 'http'
		if args.ssl:
			scheme = 'https'
		host = "%s://%s:%d" % (scheme, args.remote, args.port)
		apirequest.set_target(host)
		if args.apikey:
			apirequest.set_apikey_auth(args.apikey)
		elif args.superkey:
			apirequest.set_superkey_auth(args.superkey)

	def generic_api_response_check_failed(self, response):
		if not response.success:
			self.generic_api_response(response)

	def generic_api_response(self, response):
		if response.success:
			logging.info("Successfully executed request.")
			# TODO: Handle warnings.
			self.prettyprint(response.data)
			sys.exit(0)
		else:
			logging.error("Request failed.")
			for error in response.errors:
				logging.error(error)
			# TODO: Print errors in JSON format.
			self.prettyprint(response.data)
			self.exit(1)

class UserCreateAction(RootAction):
	def options(self, parser):
		parser.add_argument("login", help="User login name")
		parser.add_argument("email", help="Email address")
		parser.add_argument("name", help="User name")
		parser.add_argument("password", help="Password")

	def describe(self):
		return "Create a user."

	def process(self, args):
		request = paasmaker.common.api.user.UserCreateAPIRequest(None)
		request.set_user_params(args.name, args.login, args.email, True)
		request.set_user_password(args.password)
		self.point_and_auth(args, request)
		request.send(self.generic_api_response)

class UserGetAction(RootAction):
	def options(self, parser):
		parser.add_argument("user_id", help="User ID to fetch")

	def describe(self):
		return "Get a user record."

	def process(self, args):
		request = paasmaker.common.api.user.UserGetAPIRequest(None)
		request.set_user(int(args.user_id))
		self.point_and_auth(args, request)
		request.send(self.generic_api_response)

class UserEnableAction(RootAction):
	ENABLE = True

	def options(self, parser):
		parser.add_argument("user_id", help="User ID to change.")

	def describe(self):
		if self.ENABLE:
			return "Enable a user."
		else:
			return "Disable a user."

	def process(self, args):
		def user_loaded(response):
			self.generic_api_response_check_failed(response)
			request.set_user_enabled(self.ENABLE)
			request.send(self.generic_api_response)

		request = paasmaker.common.api.user.UserEditAPIRequest(None)
		self.point_and_auth(args, request)
		request.load(int(args.user_id), user_loaded)

class UserDisableAction(UserEnableAction):
	ENABLE = False

class HelpAction(RootAction):
	def options(self, parser):
		pass

	def process(self, args):
		for key, handler in ACTION_MAP.iteritems():
			logging.info("%s: %s", key, handler.describe())

		self.exit(0)

	def describe(self):
		return "Show a list of actions."

# Peek ahead at the command line options for the main action.
if len(sys.argv) == 1:
	# Nothing supplied.
	print "No module supplied. Usage: %s action" % sys.argv[0]
	print "Try %s help" % sys.argv[0]
	sys.exit(1)

action = sys.argv[1]

ACTION_MAP = {
	'user-create': UserCreateAction(),
	'user-get': UserGetAction(),
	'user-enable': UserEnableAction(),
	'user-disable': UserDisableAction(),
	'help': HelpAction()
}

# If there is no action...
if not ACTION_MAP.has_key(action):
	print "No such action %s. Try %s help" % (action, sys.argv[0])
	sys.exit(1)

# Set up our parser.
parser = argparse.ArgumentParser()
parser.add_argument('action', help="The action to perform.")

# Set up common command line options.
parser.add_argument("-r", "--remote", default="localhost", help="The pacemaker host.")
parser.add_argument("-p", "--port", type=int, default=42500, help="The pacemaker port.")
parser.add_argument("-k", "--apikey", help="User API key to authenticate with.")
parser.add_argument("--ssl", default=False, help="Use SSL to connect to the node.", action="store_true")
parser.add_argument("--superkey", default="", help="Super key to authenticate with.")
parser.add_argument("--loglevel", default="INFO", help="Log level, one of DEBUG|INFO|WARNING|ERROR|CRITICAL.")

# Now get our action to set up it's options.
ACTION_MAP[action].options(parser)

# Parse all the arguments.
args = parser.parse_args()

# Reset the log level.
logging.debug("Resetting log level to %s.", args.loglevel)
logger = logging.getLogger()
logger.setLevel(getattr(logging, args.loglevel))

logger.debug("Parsed command line arguments: %s", str(args))

# Make sure we have an auth source.
if not args.superkey and not args.apikey:
	logger.error("No API or node key passed.")
	sys.exit(1)

# Now we wait for the IO loop to start before starting.
def on_start():
	ACTION_MAP[action].process(args)

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

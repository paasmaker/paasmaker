
import logging

import paasmaker
from apirequest import APIRequest, APIResponse

import tornado

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

class NodeRegisterAPIRequest(APIRequest):

	# TODO: Override the appropriate functions to turn down the
	# connect and request timeouts.

	def build_payload(self):
		# Build our payload.
		payload = {}

		# So here's my number... call me maybe?
		payload['name'] = self.configuration.get_flat('my_name')
		payload['route'] = self.configuration.get_flat('my_route')
		payload['apiport'] = self.configuration.get_flat('http_port')

		# Send along the node tags.
		tags = {}

		# The node roles.
		roles = {}
		roles['heart'] = self.configuration.is_heart()
		roles['pacemaker'] = self.configuration.is_pacemaker()
		roles['router'] = self.configuration.is_router()

		tags['roles'] = roles

		# Runtimes.
		if self.configuration.is_heart():
			runtimes = self.configuration.get_runtimes()
			tags['runtimes'] = runtimes

		# Include node tags.
		tags['node'] = self.configuration['tags']

		payload['tags'] = tags

		logger.debug("Sending node tags: %s", str(tags))

		# For hearts, send along instance statuses.
		if self.configuration.is_heart():
			statuses = self.configuration.instances.get_instance_list()
			payload['instances'] = statuses

			logger.debug("Sending instance states: %s", str(statuses))

		return payload

	def get_endpoint(self):
		return '/node/register'

	def process_response(self, response):
		if response.success:
			# Save our nodes UUID.
			self.configuration.set_node_uuid(response.data['node']['uuid'])
		else:
			logger.error("Unable to register with master!")
			for error in response.errors:
				logger.error(error)

class NodeUpdateAPIRequest(NodeRegisterAPIRequest):
	def build_payload(self):
		payload = super(NodeUpdateAPIRequest, self).build_payload()
		payload['uuid'] = self.configuration.get_node_uuid()
		return payload

	def get_endpoint(self):
		return '/node/update'

class NodeShutdownAPIRequest(NodeUpdateAPIRequest):
	def get_endpoint(self):
		return '/node/shutdown'

class NodeUpdatePeriodicManager(object):
	def __init__(self, configuration):
		self.configuration = configuration
		# Create the periodic handler.
		self.periodic = tornado.ioloop.PeriodicCallback(
			self._node_report_in,
			configuration.get_flat('node_report_interval'),
			io_loop=configuration.io_loop
		)

		# Flag to store if the periodic has started.
		self.started = False
		# Flag to indicate that it's currently reporting to the master.
		self.reporting = False
		# Flag to indicate that it should attempt to report in again
		# immediately once it's done this report (because there is newer data).
		self.followreport = False

		# Report in now.
		self.trigger()

	def trigger(self):
		if self.reporting:
			# Already reporting, indicate that it should follow
			# this report with another one immediately.
			self.followreport = True
		else:
			# Trigger the update now.
			self._node_report_in()

	def stop(self):
		self.periodic.stop()
		self.started = False

	def _node_report_in(self):
		# Register the node with the server.
		self.reporting = True
		# Reset the follow flag.
		self.followreport = False

		# Determine the type and make the request.
		if self.configuration.get_node_uuid():
			request = paasmaker.common.api.NodeUpdateAPIRequest(self.configuration)
			request.send(self._on_registration_complete)
		else:
			request = paasmaker.common.api.NodeRegisterAPIRequest(self.configuration)
			request.send(self._on_registration_complete)

	def _on_registration_complete(self, response):
		# Start up the periodic if it's not already been done.
		if not self.started:
			self.started = True
			self.periodic.start()

		# Determine what happened.
		if not response.success or len(response.errors) > 0:
			logger.error("Unable to register with the master node.")
			for error in response.errors:
				logger.error(error)
			logger.info("Waiting until the next report interval and then we'll try again.")
		else:
			logger.info("Successfully registered or updated with master.")

		self.reporting = False

		if self.followreport:
			# Go again!
			self.trigger()
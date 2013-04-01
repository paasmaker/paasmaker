#
# Paasmaker - Platform as a Service
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#

import logging
import time

import paasmaker
from apirequest import APIRequest, APIResponse

import tornado
from pubsub import pub

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

class NodeRegisterAPIRequest(APIRequest):
	"""
	This API call is used to register a node. It's intended for
	internal use only, and you should not call it from your code.
	"""

	def async_build_payload(self, payload, callback):
		# Basic information.
		# So here's my number... call me maybe?
		payload['name'] = self.configuration.get_flat('my_name')
		payload['route'] = self.configuration.get_flat('my_route')
		payload['apiport'] = self.configuration.get_flat('http_port')
		payload['start_time'] = self.configuration.start_time

		# Send along the node tags.
		tags = {}

		# The node roles.
		roles = {}
		roles['heart'] = self.configuration.is_heart()
		roles['pacemaker'] = self.configuration.is_pacemaker()
		roles['router'] = self.configuration.is_router()

		tags['roles'] = roles

		# Include node tags.
		payload['tags'] = tags

		logger.debug("Sending node tags: %s", str(tags))

		# For hearts, send along instance statuses.
		if self.configuration.is_heart():
			statuses = self.configuration.instances.get_instance_list()
			payload['instances'] = statuses

			logger.debug("Sending instance states: %s", str(statuses))

		# Now delve into and fetch the asynchronous information.
		def payload_completed():
			# Called when all information has been gathered.
			callback(payload)

		def got_runtimes(runtimes):
			# Got the runtimes from the configuration object.
			tags['runtimes'] = runtimes
			payload_completed()

		def start_runtimes():
			if self.configuration.is_heart() or self.configuration.is_pacemaker():
				self.configuration.get_runtimes(got_runtimes)
			else:
				payload_completed()

		def got_tags(dynamic_tags):
			tags['node'] = dynamic_tags
			start_runtimes()

		def start_tags():
			self.configuration.get_dynamic_tags(got_tags)

		def got_stats(stats):
			payload['stats'] = stats
			payload['score'] = self.configuration.get_node_score(payload['stats'])

			start_tags()

		# Kick off the chain.
		self.configuration.get_node_stats(got_stats)

	def get_endpoint(self):
		return '/node/register?bypass_ssl=true'

	def process_response(self, response):
		"""
		This overriden process_response() function stores the nodes
		new UUID into our configuration.
		"""
		if response.success:
			# Save our nodes UUID.
			self.configuration.set_node_uuid(response.data['node']['uuid'])
		else:
			logger.error("Unable to register with master!")
			for error in response.errors:
				logger.error(error)

class NodeUpdateAPIRequest(NodeRegisterAPIRequest):
	"""
	Update our node record on the master. This is a subclass
	of the NodeRegisterAPIRequest that sends along the existing
	UUID.
	"""
	def async_build_payload(self, payload, callback):
		def completed_parent_payload(parent_payload):
			payload['uuid'] = self.configuration.get_node_uuid()

			callback(payload)

		super(NodeUpdateAPIRequest, self).async_build_payload(payload, completed_parent_payload)

	def get_endpoint(self):
		return '/node/update?bypass_ssl=true'

class NodeShutdownAPIRequest(NodeUpdateAPIRequest):
	"""
	Notify the master that we're shutting down, and allow it
	to take the appropriate shutdown actions.
	"""
	def get_endpoint(self):
		return '/node/shutdown?bypass_ssl=true'

class NodeUpdatePeriodicManager(object):
	"""
	A class to periodically contact the master node and let
	that node know that we're still alive, and update it on
	anything that it might have missed.
	"""
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
		# Flag to indicate if this is the first registration for this
		# node (since server startup - not the first time ever).
		self.firstregister = True

		# Report in now.
		self.trigger()

	def trigger(self):
		"""
		Trigger off a report to the master. If a report
		is already in progress, records that one must
		occur as soon as this one finishes.
		"""
		if self.reporting:
			# Already reporting, indicate that it should follow
			# this report with another one immediately.
			self.followreport = True
		else:
			# Trigger the update now.
			self._node_report_in()

	def stop(self):
		"""
		Stop periodically calling back to the master.
		Generally only used before shutting down the node.
		"""
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

			# TODO: This relies on an internal variable, but saves us having
			# to recreate the periodic.
			logger.info("Waiting for 5 seconds and then we'll try again.")
			self.periodic.callback_time = 5000
			self.periodic.stop()
			self.periodic.start()

			pub.sendMessage('node.registrationerror')
		else:
			logger.info("Successfully registered or updated with master.")

			# Reset the callback time.
			self.periodic.callback_time = self.configuration.get_flat('node_report_interval')
			self.periodic.stop()
			self.periodic.start()

			if self.firstregister:
				self.firstregister = False
				pub.sendMessage('node.firstregistration')
			else:
				pub.sendMessage('node.registrationupdate')

		self.reporting = False

		if self.followreport:
			# Go again!
			self.trigger()
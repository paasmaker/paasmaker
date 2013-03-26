import unittest
import uuid
import logging
import json
import datetime

import paasmaker
from paasmaker.common.controller import BaseController, BaseControllerTest
from paasmaker.common.core import constants

import tornado
import tornado.testing
import colander
import dateutil.parser

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

class NodeRegisterSchema(colander.MappingSchema):
	name = colander.SchemaNode(colander.String(),
		title="Node Name",
		description="A nice name for the node.")
	route = colander.SchemaNode(colander.String(),
		title="Route to this node",
		description="The route to access this node for future. Can be a DNS name of IP address.")
	apiport = colander.SchemaNode(colander.Integer(),
		title="HTTP API port",
		description="The HTTP port to use to interact with this node.")
	tags = colander.SchemaNode(colander.Mapping(unknown='preserve'),
		title="User tags",
		description="A generic set of tags or information stored for the node. Can be used to write custom placement filters, or find nodes.")
	start_time = colander.SchemaNode(colander.String(),
		title="Node start time",
		description="An ISO 8601 formatted string representing the time the node started. In UTC.")
	instances = colander.SchemaNode(colander.Mapping(unknown='preserve'),
		title="Instance status",
		description="A map of instance statuses on the node.",
		default={},
		missing={})
	stats = colander.SchemaNode(colander.Mapping(unknown='preserve'),
		title="Node stats",
		description="The stats of the node, as reported by the node.")
	score = colander.SchemaNode(colander.Float(),
		title="Node score",
		description="The node's self evaluated load score.")

class NodeUpdateSchema(NodeRegisterSchema):
	uuid = colander.SchemaNode(colander.String(),
		title="UUID",
		description="The existing UUID of the node.")

class NodeRegisterController(BaseController):
	AUTH_METHODS = [BaseController.NODE]

	def get(self):
		self.render("api/apionly.html")

	@tornado.gen.engine
	def post(self, action):
		self.action = action
		if self.action == 'register':
			valid_data = self.validate_data(NodeRegisterSchema())
		elif self.action == 'update' or self.action == 'shutdown':
			valid_data = self.validate_data(NodeUpdateSchema())

		if not valid_data:
			# Handle the very unusual case of if a HTML request
			# is tried against this controller.
			raise tornado.web.HTTPError(400, "Invalid request.")

		do_connectivity_check = False
		if self.action == 'register':
			# Look for nodes with the same route/API port.
			self.node = self._find_new_node()
			if self.node:
				do_connectivity_check = True
			else:
				raise tornado.web.HTTPError(400, "Invalid request.")

		if self.action == 'update' or self.action == 'shutdown':
			# Find the node.
			self.node = self._find_existing_node()
			if self.node:
				if self.action == 'update':
					# Only need connectivity check if we're updating.
					do_connectivity_check = True
			else:
				raise tornado.web.HTTPError(400, "Invalid request.")

		# If we're doing a connectivity check, also update the other attributes for the node.
		self.node_adjustment_jobs = []
		if do_connectivity_check:
			tags = self.params['tags']
			self.node.heart = tags['roles']['heart']
			self.node.pacemaker = tags['roles']['pacemaker']
			self.node.router = tags['roles']['router']
			self.node.tags = tags
			self.node.start_time = dateutil.parser.parse(self.params['start_time'])
			self.node.last_heard = datetime.datetime.utcnow()
			self.node.stats = self.params['stats']
			self.node.score = self.params['score']

			# Attempt to connect to the node...
			request = paasmaker.common.api.information.InformationAPIRequest(self.configuration)
			request.set_target(self.node)
			# TODO: Make the timeout configurable.
			request.send(self._finished_connectivity, connect_timeout=1.0)
		else:
			self.add_data('node', self.node.flatten())
			self._finished_response()

	def _finished_connectivity(self, response):
		if response.success:
			# Success! Save the node.
			self.session.add(self.node)
			self.session.commit()

			self.session.refresh(self.node)
			# Send back the appropriate data.
			# TODO: Figure out why it needs to be flattened now.
			# If you don't, it sends back an object with id being None.
			self.add_data('node', self.node.flatten())

			logger.info(
				"Successfully %s node %s(%s:%d) UUID %s",
				self.action,
				self.node.name,
				self.node.route,
				self.node.apiport,
				self.node.uuid
			)

			# Write the instance statuses, if needed.
			if self.node.heart:
				self._write_instance_statuses(self.params['instances'])
			else:
				self._finished_response()
		else:
			self.add_errors(response.errors)
			logger.error(
				"Failed to connect to node %s(%s:%d) UUID %s",
				self.node.name,
				self.node.route,
				self.node.apiport,
				self.node.uuid
			)
			for error in self.errors:
				logger.error(error)

			self._finished_response()

	def _finished_response(self):
		# Commit any changes to the database.
		self.session.commit()
		# Add a list of job IDs.
		self.add_data('jobs', self.node_adjustment_jobs)
		if len(self.node_adjustment_jobs) > 0:
			# Make the adjustment jobs executable.
			self.configuration.job_manager.allow_execution_list(self.node_adjustment_jobs, self._render)
		else:
			self._render()

	def _render(self):
		# Return the response.
		self.render("api/apionly.html")

	def _find_new_node(self):
		# Create a UUID for this node.
		new_uuid = str(uuid.uuid4())

		# Look for nodes with the same route/API port.
		duplicate_node = self.session.query(
			paasmaker.model.Node
		).filter(
			paasmaker.model.Node.route == self.params['route']
		).filter(
			paasmaker.model.Node.apiport == self.params['apiport']
		).first()

		if duplicate_node:
			self.add_error("Node appears to already be registered - name %s, UUID %s." % (duplicate_node.name, duplicate_node.uuid))
			return None
		else:
			node = paasmaker.model.Node(
				self.params['name'],
				self.params['route'],
				self.params['apiport'],
				new_uuid,
				constants.NODE.ACTIVE
			)
			logger.debug("New node %s(%s:%d), assigned UUID %s. Checking connectivity...", node.name, node.route, node.apiport, new_uuid)
			return node

	def _find_existing_node(self):
		# Find the node.
		node = self.session.query(
			paasmaker.model.Node
		).filter(
			paasmaker.model.Node.uuid == self.params['uuid']
		).first()

		if not node:
			self.add_error("Can't find your node record. Please register instead.")
			return None
		else:
			# Update the node.
			node.name = self.params['name']
			node.route = self.params['route']
			node.apiport = self.params['apiport']
			if self.action == 'shutdown':
				node.state = constants.NODE.STOPPED
			else:
				node.state = constants.NODE.ACTIVE
			return node

	def _write_instance_statuses(self, statuses):
		# Fetch all the instances from the database.
		if len(statuses.keys()) > 0:
			instance_list = self.session.query(
				paasmaker.model.ApplicationInstance
			).filter(
				paasmaker.model.ApplicationInstance.instance_id.in_(statuses.keys())
			).all()

			def process_instance_list():
				try:
					instance = instance_list.pop()

					def state_change_complete():
						logger.info(
							"Updating state for %s: %s -> %s",
							instance.instance_id,
							instance.state,
							statuses[instance.instance_id]
						)
						instance.state = statuses[instance.instance_id]
						self.session.add(instance)

						# Process the next one.
						process_instance_list()

						# end state_change_complete()

					if statuses.has_key(instance.instance_id):
						if instance.state != statuses[instance.instance_id]:
							# It's changed. Handle the change, and call us back when done.
							self._handle_state_change(
								instance,
								statuses[instance.instance_id],
								state_change_complete
							)
						elif statuses[instance.instance_id] == constants.INSTANCE.SUSPENDED and \
							instance.state == constants.INSTANCE.SUSPENDED:

							# It was suspended, and the pacemaker has not altered that state.
							# Start it up again.

							def on_job_submitted(job_id):
								# Make a note of the job ID.
								self.node_adjustment_jobs.append(job_id)
								# And then move on.
								process_instance_list()

								# end on_job_submitted()

							# Submit the job tree required to start up the instance.
							paasmaker.common.job.coordinate.startup.StartupRootJob.setup_instances(
								self.configuration,
								[instance],
								on_job_submitted,
								self._database_session_error
							)
						else:
							# Just process the next one.
							process_instance_list()

				except IndexError, ex:
					# No more entries.
					self._finished_response()

				# end of process_instance_list()

			# Kick off the processing.
			process_instance_list()

		else:
			# Not statuses to update.
			self._finished_response()

	def _handle_state_change(self, instance, newstate, callback):
		def update_job_added(job_id):
			self.node_adjustment_jobs.append(job_id)
			callback()

		if newstate == constants.INSTANCE.RUNNING:
			# It's now running. Insert a job to update the routing.
			paasmaker.common.job.routing.routing.RoutingUpdateJob.setup_for_instance(
				self.configuration,
				self.session,
				instance,
				True,
				update_job_added
			)
		elif newstate in [constants.INSTANCE.STOPPED, constants.INSTANCE.ERROR, constants.INSTANCE.SUSPENDED]:
			# It's no longer running (or should be removed).
			# Update it's routing. Don't attempt to start it; it's been stopped
			# for a reason.
			paasmaker.common.job.routing.routing.RoutingUpdateJob.setup_for_instance(
				self.configuration,
				self.session,
				instance,
				False,
				update_job_added
			)
		else:
			# Nothing to do.
			callback()

	@staticmethod
	def get_routes(configuration):
		routes = []
		routes.append((r"/node/(register|update|shutdown)", NodeRegisterController, configuration))
		return routes

class NodeListController(BaseController):
	AUTH_METHODS = [BaseController.SUPER, BaseController.USER]

	def get(self):
		self.require_permission(constants.PERMISSION.NODE_LIST)

		nodes = self.session.query(paasmaker.model.Node)
		self._paginate('nodes', nodes)
		self.client_side_render()

	@staticmethod
	def get_routes(configuration):
		routes = []
		routes.append((r"/node/list", NodeListController, configuration))
		return routes

class NodeBaseController(BaseController):
	AUTH_METHODS = [BaseController.SUPER, BaseController.USER]

	def _get_node(self, node_id):
		node = self.session.query(paasmaker.model.Node).get(int(node_id))
		if not node:
			raise tornado.web.HTTPError(404, "No such node.")
		self.require_permission(constants.PERMISSION.NODE_DETAIL_VIEW)
		return node


class NodeDetailController(NodeBaseController):

	def get(self, node_id):
		node = self._get_node(node_id)
		self.add_data('node', node)
		self.add_data_template('json', json)

		self.client_side_render()

	@staticmethod
	def get_routes(configuration):
		routes = []
		routes.append((r"/node/(\d+)", NodeDetailController, configuration))
		return routes

class NodeDeleteController(NodeBaseController):
	def post(self, node_id):
		node = self._get_node(node_id)
		self.require_permission(constants.PERMISSION.SYSTEM_ADMINISTRATION)

		if not node.can_delete:
			raise tornado.web.HTTPError(400, "Cannot delete node that is active.")

		self.session.delete(node)
		self.session.commit()

		self.add_data('success', True)

		self.redirect('/node/list')

	@staticmethod
	def get_routes(configuration):
		routes = []
		routes.append((r"/node/(\d+)/delete", NodeDeleteController, configuration))
		return routes

class NodeInstancesController(BaseController):
	AUTH_METHODS = [BaseController.SUPER, BaseController.USER]

	def _get_node(self, node_id):
		node = self.session.query(paasmaker.model.Node).get(int(node_id))
		if not node:
			raise tornado.web.HTTPError(404, "No such node.")
		self.require_permission(constants.PERMISSION.NODE_DETAIL_VIEW)
		return node

	def get(self, node_id):
		node = self._get_node(node_id)
		instances = []

		for instance in node.instances:
			flat = instance.flatten()
			app = {}
			app['id'] = instance.application_instance_type.application_version.application.id
			app['name'] = instance.application_instance_type.application_version.application.name
			flat['application'] = app
			ver = {}
			ver['id'] = instance.application_instance_type.application_version.id
			ver['version'] = instance.application_instance_type.application_version.version
			flat['version'] = ver
			instances.append(flat)

		self.add_data('instances', instances)
		self.render("api/apionly.html")

	@staticmethod
	def get_routes(configuration):
		routes = []
		routes.append((r"/node/(\d+)/instances", NodeInstancesController, configuration))
		return routes

class NodeControllerTest(BaseControllerTest):
	config_modules = ['pacemaker', 'heart']

	def setUp(self):
		super(NodeControllerTest, self).setUp()
		# Fire up the job manager.
		self.configuration.startup_job_manager(self.stop)
		self.wait()

	def get_app(self):
		self.late_init_configuration(self.io_loop)
		routes = NodeRegisterController.get_routes({'configuration': self.configuration})
		routes.extend(NodeListController.get_routes({'configuration': self.configuration}))
		routes.extend(paasmaker.common.controller.InformationController.get_routes({'configuration': self.configuration}))
		application = tornado.web.Application(routes, **self.configuration.get_tornado_configuration())
		return application

	def test_register(self):
		# Register the node.
		request = NodeRegisterAPIRequestLocalHost(self.configuration)
		request.send(self.stop)
		response = self.wait()

		self.failIf(not response.success)
		self.assertEquals(len(response.errors), 0, "There were errors.")
		self.assertEquals(len(response.warnings), 0, "There were warnings.")
		self.assertTrue(response.data.has_key('node'), "Missing node object in return data.")
		self.assertTrue(response.data['node'].has_key('id'), "Missing ID in return data.")
		self.assertTrue(response.data['node'].has_key('uuid'), "Missing UUID in return data.")

		self.assertEquals(self.configuration.get_node_uuid(), response.data['node']['uuid'], "Returned UUID doesn't match our UUID.")

		first_id = response.data['node']['id']

		self.configuration.get_database_session(self.stop, None)
		session = self.wait()
		node = session.query(paasmaker.model.Node).get(first_id)

		self.assertEquals(constants.NODE.ACTIVE, node.state, "Node not in correct state.")

		# Register again. This should fail, as it detects the same route/port combination.
		request = NodeRegisterAPIRequestLocalHost(self.configuration)
		request.send(self.stop)
		response = self.wait()

		self.failIf(response.success)

		# Now update our node.
		request = NodeUpdateAPIRequestLocalHost(self.configuration)
		request.send(self.stop)
		response = self.wait()

		self.failIf(not response.success)
		self.assertEquals(len(response.errors), 0, "There were errors.")
		self.assertEquals(len(response.warnings), 0, "There were warnings.")
		self.assertTrue(response.data.has_key('node'), "Missing node object in return data.")
		self.assertTrue(response.data['node'].has_key('id'), "Missing ID in return data.")
		self.assertTrue(response.data['node'].has_key('uuid'), "Missing UUID in return data.")
		self.assertEquals(first_id, response.data['node']['id'], "Updated ID is different to original.")

		session.refresh(node)
		self.assertEquals(constants.NODE.ACTIVE, node.state, "Node not in correct state.")

		# Test the listing of nodes here too.
		request = paasmaker.common.api.nodelist.NodeListAPIRequest(self.configuration)
		request.set_superkey_auth()
		request.send(self.stop)
		response = self.wait()

		self.failIf(not response.success)
		self.assertEquals(len(response.errors), 0, "There were errors.")
		self.assertEquals(len(response.warnings), 0, "There were warnings.")
		self.assertTrue(response.data.has_key('nodes'), "Missing nodes list.")
		self.assertEquals(len(response.data['nodes']), 1, "Not the expected number of nodes.")

		# Finally, shutdown the node.
		request = NodeShutdownAPIRequestLocalHost(self.configuration)
		request.send(self.stop)
		response = self.wait()

		self.failIf(not response.success)
		self.assertEquals(len(response.errors), 0, "There were errors.")
		self.assertEquals(len(response.warnings), 0, "There were warnings.")
		self.assertTrue(response.data.has_key('node'), "Missing node object in return data.")
		self.assertTrue(response.data['node'].has_key('id'), "Missing ID in return data.")
		self.assertTrue(response.data['node'].has_key('uuid'), "Missing UUID in return data.")
		self.assertEquals(first_id, response.data['node']['id'], "Updated ID is different to original.")

		session.refresh(node)
		self.assertEquals(constants.NODE.STOPPED, node.state, "Node not in correct state.")

	def test_update_instances(self):
		# Register the node.
		request = NodeRegisterAPIRequestLocalHost(self.configuration)
		request.send(self.stop)
		response = self.wait()

		self.failIf(not response.success)
		self.assertEquals(len(response.errors), 0, "There were errors.")
		self.assertEquals(len(response.warnings), 0, "There were warnings.")
		self.assertTrue(response.data.has_key('node'), "Missing node object in return data.")
		self.assertTrue(response.data['node'].has_key('id'), "Missing ID in return data.")
		self.assertTrue(response.data['node'].has_key('uuid'), "Missing UUID in return data.")

		self.assertEquals(self.configuration.get_node_uuid(), response.data['node']['uuid'], "Returned UUID doesn't match our UUID.")

		first_id = response.data['node']['id']

		# Create a few instances.
		self.configuration.get_database_session(self.stop, None)
		session = self.wait()
		node = session.query(paasmaker.model.Node).get(first_id)

		workspace = paasmaker.model.Workspace()
		workspace.name = 'Test'
		workspace.stub = 'test'

		application = paasmaker.model.Application()
		application.workspace = workspace
		application.name = 'foo.com'

		application_version = paasmaker.model.ApplicationVersion()
		application_version.application = application
		application_version.version = 1
		application_version.is_current = False
		application_version.manifest = ''
		application_version.source_path = "paasmaker://%s/%s" % (self.configuration.get_node_uuid(), "none.tar.gz")
		application_version.source_checksum = 'dummychecksumhere'
		application_version.state = paasmaker.common.core.constants.VERSION.PREPARED
		application_version.scm_name = 'paasmaker.scm.zip'
		application_version.scm_parameters = {}

		instance_type = paasmaker.model.ApplicationInstanceType()
		instance_type.application_version = application_version
		instance_type.name = 'web'
		instance_type.quantity = 1
		instance_type.runtime_name = 'paasmaker.runtime.shell'
		instance_type.runtime_parameters = {}
		instance_type.runtime_version = '1'
		instance_type.startup = {}
		instance_type.placement_provider = 'paasmaker.placement.default'
		instance_type.placement_parameters = {}
		instance_type.exclusive = False
		instance_type.standalone = False

		instance = paasmaker.model.ApplicationInstance()
		instance.instance_id = str(uuid.uuid4())
		instance.application_instance_type = instance_type
		instance.node = node
		instance.state = paasmaker.common.core.constants.INSTANCE.STARTING
		instance.port = self.configuration.get_free_port()

		session.add(instance)
		session.commit()
		session.refresh(instance)

		instance_data = instance.flatten_for_heart()
		self.configuration.instances.add_instance(instance.instance_id, instance_data)

		# Now update our node.
		request = NodeUpdateAPIRequestLocalHost(self.configuration)
		request.send(self.stop)
		response = self.wait()

		self.failIf(not response.success)
		self.assertEquals(len(response.errors), 0, "There were errors.")
		self.assertEquals(len(response.warnings), 0, "There were warnings.")
		self.assertTrue(response.data.has_key('node'), "Missing node object in return data.")
		self.assertTrue(response.data['node'].has_key('id'), "Missing ID in return data.")
		self.assertTrue(response.data['node'].has_key('uuid'), "Missing UUID in return data.")
		self.assertEquals(first_id, response.data['node']['id'], "Updated ID is different to original.")

		# Check that it's still in the correct state.
		session.refresh(instance)
		self.assertEquals(instance.state, constants.INSTANCE.STARTING, "Instance was not in expected state.")

		# Change the instance status in the local store, and then update again.
		instance_data['instance']['state'] = constants.INSTANCE.RUNNING
		session.refresh(instance)
		self.assertEquals(instance.state, constants.INSTANCE.STARTING, "Instance was not in expected state.")

		request = NodeUpdateAPIRequestLocalHost(self.configuration)
		request.send(self.stop)
		response = self.wait()

		self.failIf(not response.success)
		self.assertEquals(len(response.errors), 0, "There were errors.")
		self.assertEquals(len(response.warnings), 0, "There were warnings.")
		self.assertTrue(response.data.has_key('node'), "Missing node object in return data.")
		self.assertTrue(response.data['node'].has_key('id'), "Missing ID in return data.")
		self.assertTrue(response.data['node'].has_key('uuid'), "Missing UUID in return data.")
		self.assertEquals(first_id, response.data['node']['id'], "Updated ID is different to original.")

		# Should also have returned one job.
		# TODO: Do a more exhaustive check than this.
		self.assertEquals(len(response.data['jobs']), 1, "Didn't queue up a job.")

		# Change the instance status in the local store, and then update again.
		instance_data['instance']['state'] = constants.INSTANCE.ERROR
		session.refresh(instance)
		self.assertEquals(instance.state, constants.INSTANCE.RUNNING, "Instance was not in expected state.")

		request = NodeUpdateAPIRequestLocalHost(self.configuration)
		request.send(self.stop)
		response = self.wait()

		self.failIf(not response.success)
		self.assertEquals(len(response.errors), 0, "There were errors.")
		self.assertEquals(len(response.warnings), 0, "There were warnings.")

		# Should also have returned one job.
		# TODO: Do a more exhaustive check than this.
		self.assertEquals(len(response.data['jobs']), 1, "Didn't queue up a job.")

		# And refresh and check the database version changed.
		session.refresh(instance)
		self.assertEquals(instance.state, constants.INSTANCE.ERROR, "Instance was not updated.")

	def test_fail_connect_port(self):
		# Test when it can't connect.
		request = NodeRegisterAPIRequestFailPort(self.configuration)
		request.send(self.stop)
		response = self.wait()

		self.failIf(response.success)
		self.assertEquals(len(response.errors), 2, "There were no errors.")
		self.assertEquals(len(response.warnings), 0, "There were warnings.")

	def test_fail_update_no_exist(self):
		request = NodeUpdateAPIRequestFailUUID(self.configuration)
		request.send(self.stop)
		response = self.wait()

		self.failIf(response.success)
		self.assertEquals(len(response.errors), 3, "There were no errors.")
		self.assertEquals(len(response.warnings), 0, "There were warnings.")

	def test_fail_connect_host(self):
		# Test when it can't connect.
		request = NodeRegisterAPIRequestFailHost(self.configuration)
		request.send(self.stop)
		response = self.wait()

		self.failIf(response.success)
		self.assertEquals(len(response.errors), 2, "There were no errors.")
		self.assertEquals(len(response.warnings), 0, "There were warnings.")

class NodeRegisterAPIRequestLocalHost(paasmaker.common.api.NodeRegisterAPIRequest):
	"""
	Stub class to send back localhost as the route - on some machines,
	the local path detection causes the unit tests to fail.
	"""
	def async_build_payload(self, payload, callback):
		def parent_payload_done(parent_data):
			payload['route'] = 'localhost'
			callback(payload)

		super(NodeRegisterAPIRequestLocalHost, self).async_build_payload(payload, parent_payload_done)

class NodeUpdateAPIRequestLocalHost(paasmaker.common.api.NodeUpdateAPIRequest):
	"""
	Stub class to send back localhost as the route - on some machines,
	the local path detection causes the unit tests to fail.
	"""
	def async_build_payload(self, payload, callback):
		def parent_payload_done(parent_data):
			payload['route'] = 'localhost'
			callback(payload)

		super(NodeUpdateAPIRequestLocalHost, self).async_build_payload(payload, parent_payload_done)

class NodeShutdownAPIRequestLocalHost(paasmaker.common.api.NodeShutdownAPIRequest):
	"""
	Stub class to send back localhost as the route - on some machines,
	the local path detection causes the unit tests to fail.
	"""
	def async_build_payload(self, payload, callback):
		def parent_payload_done(parent_data):
			payload['route'] = 'localhost'
			callback(payload)

		super(NodeShutdownAPIRequestLocalHost, self).async_build_payload(payload, parent_payload_done)

class NodeRegisterAPIRequestFailPort(paasmaker.common.api.NodeRegisterAPIRequest):
	"""
	Stub class to send back a faulty HTTP port, to stop it from accessing the remote end.
	"""
	def async_build_payload(self, payload, callback):
		def parent_payload_done(parent_data):
			payload['apiport'] += 1000
			callback(payload)

		super(NodeRegisterAPIRequestFailPort, self).async_build_payload(payload, parent_payload_done)

class NodeRegisterAPIRequestFailHost(paasmaker.common.api.NodeRegisterAPIRequest):
	"""
	Stub class to send back a faulty route, to stop it from accessing the remote end.
	"""
	def async_build_payload(self, payload, callback):
		def parent_payload_done(parent_data):
			payload['route'] = 'noexist.paasmaker.com'
			callback(payload)

		super(NodeRegisterAPIRequestFailHost, self).async_build_payload(payload, parent_payload_done)

class NodeUpdateAPIRequestFailUUID(paasmaker.common.api.NodeUpdateAPIRequest):
	"""
	Stub class to send back a faulty UUID.
	"""
	def async_build_payload(self, payload, callback):
		def parent_payload_done(parent_data):
			payload['uuid'] = 'no node to see here'
			callback(payload)

		super(NodeUpdateAPIRequestFailUUID, self).async_build_payload(payload, parent_payload_done)
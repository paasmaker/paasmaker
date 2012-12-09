import unittest
import uuid
import logging
import json

import paasmaker
from paasmaker.common.controller import BaseController, BaseControllerTest
from paasmaker.common.core import constants

import tornado
import tornado.testing
import colander

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
	instances = colander.SchemaNode(colander.Mapping(unknown='preserve'),
		title="Instance status",
		description="A map of instance statuses on the node.",
		default={},
		missing={})

class NodeUpdateSchema(NodeRegisterSchema):
	uuid = colander.SchemaNode(colander.String(),
		title="UUID",
		description="The existing UUID of the node.")

class NodeRegisterController(BaseController):
	AUTH_METHODS = [BaseController.NODE]

	def get(self):
		self.render("api/apionly.html")

	@tornado.web.asynchronous
	@tornado.gen.engine
	def post(self, action):
		if action == 'register':
			self.validate_data(NodeRegisterSchema())
		elif action == 'update':
			self.validate_data(NodeUpdateSchema())

		do_connectivity_check = False
		if action == 'register':
			# Create a UUID for this node.
			new_uuid = str(uuid.uuid4())

			# Look for nodes with the same route/API port.
			duplicate_node = self.db().query(paasmaker.model.Node) \
				.filter(paasmaker.model.Node.route==self.params['route']) \
				.filter(paasmaker.model.Node.apiport==self.params['apiport']).first()

			if duplicate_node:
				self.add_error("Node appears to already be registered - name %s, UUID %s." % (duplicate_node.name, duplicate_node.uuid))
			else:
				node = paasmaker.model.Node(self.params['name'], self.params['route'], self.params['apiport'], new_uuid, constants.NODE.ACTIVE)
				logger.debug("New node %s(%s:%d), assigned UUID %s. Checking connectivity...", node.name, node.route, node.apiport, new_uuid)
				do_connectivity_check = True

		if action == 'update':
			# Find the node.
			node = self.db().query(paasmaker.model.Node) \
				.filter(paasmaker.model.Node.uuid==self.params['uuid']).first()

			if not node:
				self.add_error("Can't find your node record. Please register instead.")
			else:
				# Update the node.
				node.name = self.params['name']
				node.route = self.params['route']
				node.apiport = self.params['apiport']
				node.state = constants.NODE.ACTIVE
				do_connectivity_check = True

		# If we're doing a connectivity check, also update the other attributes for the node.
		if do_connectivity_check:
			tags = self.params['tags']
			node.heart = tags['roles']['heart']
			node.pacemaker = tags['roles']['pacemaker']
			node.router = tags['roles']['router']

			node.tags = tags

		if do_connectivity_check:
			# Attempt to connect to the node...
			request = paasmaker.common.api.information.InformationAPIRequest(self.configuration)
			request.set_target(node)
			# TODO: Make the timeout configurable.
			response = yield tornado.gen.Task(request.send, connect_timeout=1.0)
			if response.success:
				# Success! Save the node.
				session = self.db()
				session.add(node)
				session.commit()

				# Send back the appropriate data.
				self.add_data('node', node)
				logger.info("Successfully %s node %s(%s:%d) UUID %s", action, node.name, node.route, node.apiport, node.uuid)

				# Write the instance statuses.
				if node.heart:
					self._write_instance_statuses(self.params['instances'])
			else:
				self.add_errors(response.errors)
				logger.error("Failed to connect to node %s(%s:%d) UUID %s", node.name, node.route, node.apiport, node.uuid)
				for error in self.errors:
					logger.error(error)

		# Return the response.
		self.render("api/apionly.html")

	def _write_instance_statuses(self, statuses):
		# Fetch all the instances from the database.
		if len(statuses.keys()) > 0:
			session = self.db()
			instances = session.query(
				paasmaker.model.ApplicationInstance
			).filter(
				paasmaker.model.ApplicationInstance.instance_id.in_(statuses.keys())
			)

			# Now, for each instance...
			for instance in instances:
				if instance.state != statuses[instance.instance_id]:
					logger.info("Updating state for %s: %s -> %s", instance.instance_id, instance.state, statuses[instance.instance_id])
					instance.state = statuses[instance.instance_id]
					session.add(instance)

			# And save to the DB.
			session.commit()

	@staticmethod
	def get_routes(configuration):
		routes = []
		routes.append((r"/node/(register|update)", NodeRegisterController, configuration))
		return routes

class NodeListController(BaseController):
	AUTH_METHODS = [BaseController.SUPER, BaseController.USER]

	def get(self):
		self.require_permission(constants.PERMISSION.NODE_LIST)

		# TODO: Paginate...
		nodes = self.db().query(paasmaker.model.Node)
		self.add_data('nodes', nodes)
		self.render("node/list.html")

	@staticmethod
	def get_routes(configuration):
		routes = []
		routes.append((r"/node/list", NodeListController, configuration))
		return routes

class NodeDetailController(BaseController):
	AUTH_METHODS = [BaseController.SUPER, BaseController.USER]

	def _get_node(self, node_id):
		node = self.db().query(paasmaker.model.Node).get(int(node_id))
		if not node:
			raise tornado.web.HTTPError(404, "No such node.")
		self.require_permission(constants.PERMISSION.NODE_DETAIL_VIEW)
		return node

	@tornado.web.asynchronous
	def get(self, node_id):
		node = self._get_node(node_id)

		self.add_data('node', node)

		# Fetch the router stats.
		self._get_router_stats_for('node', node.id, self._got_stats)

	def _got_stats(self, result):
		self.render("node/detail.html")

	@staticmethod
	def get_routes(configuration):
		routes = []
		routes.append((r"/node/(\d+)", NodeDetailController, configuration))
		return routes

class NodeControllerTest(BaseControllerTest):
	config_modules = ['pacemaker', 'heart']

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
		session = self.configuration.get_database_session()
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
		instance.state = paasmaker.common.core.constants.INSTANCE.RUNNING

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
		# TODO: Figure out why we're getting a new ORM object back... but only here...
		#self.assertEquals(first_id, response.data['node']['id'], "Updated ID is different to original.")

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
		self.assertEquals(len(response.errors), 1, "There were no errors.")
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
	def build_payload(self):
		data = super(NodeRegisterAPIRequestLocalHost, self).build_payload()
		data['route'] = 'localhost'
		return data

class NodeUpdateAPIRequestLocalHost(paasmaker.common.api.NodeUpdateAPIRequest):
	"""
	Stub class to send back localhost as the route - on some machines,
	the local path detection causes the unit tests to fail.
	"""
	def build_payload(self):
		data = super(NodeUpdateAPIRequestLocalHost, self).build_payload()
		data['route'] = 'localhost'
		return data

class NodeRegisterAPIRequestFailPort(paasmaker.common.api.NodeRegisterAPIRequest):
	"""
	Stub class to send back a faulty HTTP port, to stop it from accessing the remote end.
	"""
	def build_payload(self):
		data = super(NodeRegisterAPIRequestFailPort, self).build_payload()
		data['apiport'] += 1000
		return data

class NodeRegisterAPIRequestFailHost(paasmaker.common.api.NodeRegisterAPIRequest):
	"""
	Stub class to send back a faulty route, to stop it from accessing the remote end.
	"""
	def build_payload(self):
		data = super(NodeRegisterAPIRequestFailHost, self).build_payload()
		data['route'] = 'noexist.paasmaker.com'
		return data

class NodeUpdateAPIRequestFailUUID(paasmaker.common.api.NodeUpdateAPIRequest):
	"""
	Stub class to send back a faulty UUID.
	"""
	def build_payload(self):
		data = super(NodeUpdateAPIRequestFailUUID, self).build_payload()
		data['uuid'] = 'no node to see here'
		return data
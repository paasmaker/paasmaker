import unittest
import paasmaker
import uuid
import logging
from paasmaker.common.controller import BaseController, BaseControllerTest

import tornado
import tornado.testing

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

class NodeController(BaseController):
	auth_methods = [BaseController.NODE]

	def get(self):
		self.render("api/apionly.html")

	@tornado.web.asynchronous
	@tornado.gen.engine
	def post(self):
		# TODO: Check schema!
		# TODO: Better initial state for the node. Ie, Map the states!
		# TODO: Check for duplicates!
		# Create a UUID for this node.
		new_uuid = str(uuid.uuid4())
		node = paasmaker.model.Node(self.param('name'), self.param('route'), self.param('apiport'), new_uuid, 'NEW')
		logger.debug("New node %s(%s:%d), assigned UUID %s. Checking connectivity...", node.name, node.route, node.apiport, new_uuid)
		# Attempt to connect to the node...
		request = paasmaker.common.api.information.InformationAPIRequest(self.configuration, self.io_loop)
		request.set_target(node)
		response = yield tornado.gen.Task(request.send, connect_timeout=1.0)
		if response.success:
			session = self.db()
			session.add(node)
			session.commit()

			self.add_data('uuid', new_uuid)
			self.add_data('id', node.id)
			logger.info("Successfully registered node %s(%s:%d) UUID %s", node.name, node.route, node.apiport, new_uuid)
		else:
			self.add_errors(response.errors)
			logger.error("Failed to connect to new node:")
			for error in self.errors:
				logger.error(error)
		self.render("api/apionly.html")
		self.finish()

	@staticmethod
	def get_routes(configuration):
		routes = []
		routes.append((r"/node/register", NodeController, configuration))
		return routes

class NodeControllerTest(BaseControllerTest):
	config_modules = ['pacemaker']

	def get_app(self):
		self.late_init_configuration()
		routes = NodeController.get_routes({'configuration': self.configuration, 'io_loop': self.io_loop})
		routes.extend(paasmaker.common.controller.InformationController.get_routes({'configuration': self.configuration}))
		application = tornado.web.Application(routes, **self.configuration.get_tornado_configuration())
		return application

	def test_register(self):
		request = paasmaker.common.api.NodeRegisterAPIRequest(self.configuration, self.io_loop)
		request.send(self.stop)
		response = self.wait()

		self.failIf(not response.success)
		self.assertEquals(len(response.errors), 0, "There were errors.")
		self.assertEquals(len(response.warnings), 0, "There were warnings.")
		self.assertTrue(response.data.has_key('uuid'))
		self.assertTrue(response.data.has_key('id'))

	def test_fail_connect_port(self):
		# Test when it can't connect.
		request = NodeRegisterAPIRequestFailPort(self.configuration, self.io_loop)
		request.send(self.stop)
		response = self.wait()

		self.failIf(response.success)
		self.assertEquals(len(response.errors), 1, "There were no errors.")
		self.assertEquals(len(response.warnings), 0, "There were warnings.")

	def test_fail_connect_host(self):
		# Test when it can't connect.
		request = NodeRegisterAPIRequestFailHost(self.configuration, self.io_loop)
		request.send(self.stop)
		response = self.wait()

		self.failIf(response.success)
		self.assertEquals(len(response.errors), 1, "There were no errors.")
		self.assertEquals(len(response.warnings), 0, "There were warnings.")

class NodeRegisterAPIRequestFailPort(paasmaker.common.api.NodeRegisterAPIRequest):
	"""
	Stub class to send back a faulty HTTP port, to stop it from accessing the remote end.
	"""
	def build_payload(self):
		# The use of super() didn't work here, and I couldn't figure it out after
		# 20 minutes of Googling. TODO: Fix this properly.
		data = paasmaker.common.api.NodeRegisterAPIRequest.build_payload(self)
		data['apiport'] += 1000
		return data

class NodeRegisterAPIRequestFailHost(paasmaker.common.api.NodeRegisterAPIRequest):
	"""
	Stub class to send back a faulty HTTP port, to stop it from accessing the remote end.
	"""
	def build_payload(self):
		# The use of super() didn't work here, and I couldn't figure it out after
		# 20 minutes of Googling. TODO: Fix this properly.
		data = paasmaker.common.api.NodeRegisterAPIRequest.build_payload(self)
		data['route'] = 'noexist.paasmaker.com'
		return data
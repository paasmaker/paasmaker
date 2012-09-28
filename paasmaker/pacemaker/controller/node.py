import unittest
import paasmaker
import uuid
from paasmaker.common.controller import BaseController, BaseControllerTest

import tornado
import tornado.testing

class NodeController(BaseController):
	auth_methods = [BaseController.NODE]

	def get(self):
		self.render("api/apionly.html")

	@tornado.web.asynchronous
	@tornado.gen.engine
	def post(self):
		# TODO: Check schema!
		# TODO: Better initial state for the node. Ie, Map the states!
		# Create a UUID for this node.
		new_uuid = str(uuid.uuid4())
		node = paasmaker.model.Node(self.param('name'), self.param('route'), self.param('apiport'), new_uuid, 'NEW')
		# Attempt to connect to the node...
		# TODO: Set low connect timeout.
		request = paasmaker.common.api.information.InformationAPIRequest(self.configuration, self.io_loop)
		request.set_target(node)
		response = yield tornado.gen.Task(request.send, connect_timeout=1.0)
		if response.success:
			session = self.db()
			session.add(node)
			session.commit()

			self.add_data('uuid', new_uuid)
			self.add_data('id', node.id)
		else:
			self.add_errors(response.errors)
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

		# TODO: Test when it can't connect back.

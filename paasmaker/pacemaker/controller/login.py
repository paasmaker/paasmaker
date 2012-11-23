
from paasmaker.common.controller import InformationController
import paasmaker
from paasmaker.common.controller import BaseController, BaseControllerTest
import tornado

import unittest

class LoginController(BaseController):
	AUTH_METHODS = [BaseController.ANONYMOUS]

	def get(self):
		self.render("login/login.html")

	@tornado.web.asynchronous
	def post(self):
		# Check the username/password supplied.
		username = self.param('username')
		password = self.param('password')

		# Find auth plugins.
		plugins = self.configuration.plugins.plugins_for(paasmaker.util.plugin.MODE.USER_AUTHENTICATE_PLAIN)
		plugins.reverse()

		# And with each of them, try to authenticate.
		session = self.db()

		def complete_request(authenticated):
			if authenticated:
				# Note: redirect() calls finish().
				ret = self.param('rt')
				if ret:
					self.redirect(ret)
				else:
					self.redirect('/')
			else:
				self.add_error("Unable to authenticate you.")
				self.render("login/login.html")
				self.finish()

		def try_plugin(plugin):
			login_handler = self.configuration.plugins.instantiate(
				plugin,
				paasmaker.util.plugin.MODE.USER_AUTHENTICATE_PLAIN
			)

			def success_login(user, message):
				# Success! Record that user.
				self.allow_user(user)
				complete_request(True)

			def failed_login(reason, message):
				# Add it as a warning.
				self.add_warning("%s: %s", (plugin, message))

				# And move onto the next plugin.
				# Unless there are no more.
				if len(plugins) == 0:
					complete_request(False)
				else:
					try_plugin(plugins.pop())

			login_handler.authenticate(
				session,
				username,
				password,
				success_login,
				failed_login
			)

		# And kick off the first plugin.
		if len(plugins) == 0:
			self.add_error("Server is misconfigured - we know of no way to authenticate you.")
			complete_request(False)
		else:
			try_plugin(plugins.pop())

	def allow_user(self, user):
		self.set_secure_cookie("user", unicode(user.id))
		self.add_data('success', True)
		# Token is not for use with the auth token authentication method - because
		# it expires. Instead, it's supplied back as a cookie and in the data for
		# unit tests or other short lived systems.
		self.add_data('token', self.create_signed_value('user', unicode(user.id)))

	@staticmethod
	def get_routes(configuration):
		routes = []
		routes.append((r"/login", LoginController, configuration))
		return routes

class LogoutController(BaseController):
	AUTH_METHODS = [BaseController.USER]

	def get(self):
		self.post()

	def post(self):
		self.clear_cookie('user')
		self.redirect('/')

	@staticmethod
	def get_routes(configuration):
		routes = []
		routes.append((r"/logout", LogoutController, configuration))
		return routes

class LoginControllerTest(BaseControllerTest):
	config_modules = ['pacemaker']

	def get_app(self):
		self.late_init_configuration(self.io_loop)
		routes = LoginController.get_routes({'configuration': self.configuration})
		routes.extend(LogoutController.get_routes({'configuration': self.configuration}))
		routes.extend(InformationController.get_routes({'configuration': self.configuration}))
		application = tornado.web.Application(routes, **self.configuration.get_tornado_configuration())
		return application

	def test_login(self):
		# Create a test user.
		s = self.configuration.get_database_session()
		u = paasmaker.model.User()
		u.login = 'username'
		u.email = 'username@example.com'
		u.name = 'User Name'
		u.password = 'test'
		s.add(u)
		s.commit()

		# Ok, now that we've done that, try to log in.
		body = "username=username&password=test"
		request = tornado.httpclient.HTTPRequest(
			"http://localhost:%d/login" % self.get_http_port(),
			method="POST",
			body=body,
			follow_redirects=False)
		client = tornado.httpclient.AsyncHTTPClient(io_loop=self.io_loop)
		client.fetch(request, self.stop)
		response = self.wait()
		self.assertEquals(response.code, 302, "Should have 302 redirected.")
		self.assertEquals(response.headers['Location'], '/', "Should have redirected to homepage.")
		self.assertTrue(response.headers.has_key('Set-Cookie'), "Missing user cookie.")

	def test_login_json(self):
		# Create a test user.
		s = self.configuration.get_database_session()
		u = paasmaker.model.User()
		u.login = 'username'
		u.email = 'username@example.com'
		u.name = 'User Name'
		u.password = 'test'
		s.add(u)
		s.commit()
		s.refresh(u)

		# Ok, now that we've done that, try to log in.
		request = paasmaker.common.api.LoginAPIRequest(self.configuration)
		request.set_credentials('username', 'test')
		request.send(self.stop)
		response = self.wait()

		self.failIf(not response.success)
		self.assertEquals(len(response.errors), 0, "There were errors.")
		self.assertEquals(len(response.warnings), 0, "There were warnings.")
		self.assertTrue(response.data.has_key('token'))

		# Test that the supplied token is valid.
		auth_token = response.data['token']

		request = tornado.httpclient.HTTPRequest(
			"http://localhost:%d/information" % self.get_http_port(),
			headers={'Cookie': 'user=' + auth_token})
		client = tornado.httpclient.AsyncHTTPClient(io_loop=self.io_loop)
		client.fetch(request, self.stop)
		response = self.wait()

		# Check that it returned the information page.
		self.failIf(response.error)
		self.assertIn("machine readable", response.body)

		# Try again with the HTTP header token.
		request = tornado.httpclient.HTTPRequest(
			"http://localhost:%d/information" % self.get_http_port(),
			headers={'User-Token': u.apikey})
		client = tornado.httpclient.AsyncHTTPClient(io_loop=self.io_loop)
		client.fetch(request, self.stop)
		response = self.wait()

		# Check that it returned the information page.
		self.failIf(response.error)
		self.assertIn("machine readable", response.body)

	def test_login_apikey(self):
		# Create a test user.
		s = self.configuration.get_database_session()
		u = paasmaker.model.User()
		u.login = 'username'
		u.email = 'username@example.com'
		u.name = 'User Name'
		u.password = 'test'
		s.add(u)
		s.commit()
		s.refresh(u)

		request = paasmaker.common.api.InformationAPIRequest(self.configuration)
		request.set_apikey_auth('bogus')
		request.send(self.stop)
		response = self.wait()

		# This will fail.
		self.failIf(response.success)

		# Try it again with the key.
		request = paasmaker.common.api.InformationAPIRequest(self.configuration)
		request.set_apikey_auth(u.apikey)
		request.send(self.stop)
		response = self.wait()

		# This should succeed.
		self.failIf(not response.success)
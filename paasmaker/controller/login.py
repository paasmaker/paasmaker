#!/usr/bin/env python

from base import BaseController
from base import BaseControllerTest
import paasmaker
import tornado

import unittest

class LoginController(BaseController):
	auth_methods = [BaseController.ANONYMOUS]

	def get(self):
		self.render("login/login.html")

	def post(self):
		# Check the username/password supplied.
		# Only internal auth is supported here.
		username = self.param('username')
		password = self.param('password')
		user = self.db().query(paasmaker.model.User) \
			.filter(paasmaker.model.User.userkey==username).first()
		success = False

		if user:
			# Found that user. Check their authentication.
			if user.auth_source == 'internal':
				if user.check_password(password):
					self.allow_user(user)
					success = True
				else:
					self.add_error("Invalid username or password.")
			# TODO: Other authentication sources...
		else:
			self.add_error("Invalid username or password.")

		if success and self.format == 'html':
			ret = self.param('rt')
			if ret:
				self.redirect(ret)
			else:
				self.redirect('/')
		else:
			self.render("login/login.html")

	def allow_user(self, user):
		self.set_secure_cookie("user", unicode(user.id))
		self.add_data('success', True)
		self.add_data('token', self.create_signed_value('user', unicode(user.id)))

	@staticmethod
	def get_routes(configuration):
		routes = []
		routes.append((r"/login", LoginController, configuration))
		return routes

class LogoutController(BaseController):
	auth_methods = [BaseController.USER]

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
		routes = LoginController.get_routes({'configuration': self.configuration})
		routes.extend(LogoutController.get_routes({'configuration': self.configuration}))
		application = tornado.web.Application(routes, **self.configuration.get_tornado_configuration())
		return application

	def test_login(self):
		# Create a test user.
		s = self.configuration.get_database_session()
		u = paasmaker.model.User('danielf', 'freefoote@dview.net')
		u.set_password('test')
		s.add(u)
		s.commit()

		# Ok, now that we've done that, try to log in.
		body = "username=danielf&password=test"
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
		u = paasmaker.model.User('danielf', 'freefoote@dview.net')
		u.set_password('test')
		s.add(u)
		s.commit()

		# Ok, now that we've done that, try to log in.
		request = paasmaker.util.apirequest.APIRequest(self.configuration, self.io_loop)
		request.send(self.get_url('/login?format=json'), {'username': 'danielf', 'password': 'test'}, self.stop)
		response = self.wait()

		self.failIf(not response.success)
		self.assertEquals(len(response.errors), 0, "There were errors.")
		self.assertEquals(len(response.warnings), 0, "There were warnings.")
		self.assertTrue(response.data.has_key('token'))
		# TODO: Test that this token can be used for token-authenticated API requests.
		#print response.data['token']

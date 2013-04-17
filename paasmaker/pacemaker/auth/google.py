#
# Paasmaker - Platform as a Service
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#

import paasmaker

from paasmaker.common.controller.base import BaseController

import colander
import tornado
import tornado.auth

# TODO: Allow auto-assigning a role.

class GoogleAuthConfigurationSchema(colander.MappingSchema):
	limit_domains = colander.SchemaNode(
		colander.String(),
		title="Limit login domain names",
		description="Limit login domain names to the comma seperated list provided. If a user has an email that doesn't match, they are not permitted to log in.",
		default=None,
		missing=None
	)

class GoogleAuthMetadata(paasmaker.util.plugin.Plugin):
	MODES = {
		paasmaker.util.plugin.MODE.USER_AUTHENTICATE_EXTERNAL: None,
		paasmaker.util.plugin.MODE.STARTUP_ROUTES: None,
	}
	OPTIONS_SCHEMA = GoogleAuthConfigurationSchema()
	API_VERSION = "0.9.0"

	def add_routes(self, routes, route_extras):
		# Add the additional route required.
		routes.extend(
			GoogleAuthController.get_routes(route_extras, self.called_name, self.options)
		)

	def get_login_metadata(self):
		return {
			'uri': '/login/%s' % self.called_name,
			'text': 'Google',
			'image': None
		}

class GoogleAuthController(BaseController, tornado.auth.GoogleMixin):
	AUTH_METHODS = [BaseController.ANONYMOUS]

	def initialize(self, **kwargs):
		# Take out our kwargs.
		self.called_name = kwargs['called_name']
		self.options = kwargs['options']

		del kwargs['called_name']
		del kwargs['options']

		super(GoogleAuthController, self).initialize(**kwargs)

	def get(self):
		if self.get_argument("openid.mode", None):
			self.get_authenticated_user(self.async_callback(self._on_auth))
			return
		self.authenticate_redirect()

	@tornado.gen.engine
	def _on_auth(self, google_user):
		if not google_user:
			raise tornado.web.HTTPError(500, "Google auth failed")

		# Split up the allowed email names.
		if self.options['limit_domains']:
			limited_list = self.options['limit_domains'].split(',')
			allowed = False
			for domain in limited_list:
				domain = domain.strip()

				if google_user['email'].endswith(domain):
					allowed = True

			if not allowed:
				raise tornado.web.HTTPError(403, "Not permitted to log in to this server.")

		# The google_user dict has the following keys:
		# first_name
		# name
		# claimed_id
		# locale
		# last_name
		# email

		# Look up the user by email address.
		user = self.session.query(
			paasmaker.model.User
		).filter(
			paasmaker.model.User.login==google_user['email'],
			paasmaker.model.User.auth_source==self.called_name
		).first()

		if not user:
			# Create the user record. They won't have any permissions
			# at this stage.
			user = paasmaker.model.User()
			user.login = google_user['email']
			user.email = google_user['email']
			user.name = google_user['name']
			user.password = "none"
			# TODO: Use the correct plugin name.
			user.auth_source = "paasmaker.auth.google"
			user.auth_meta = google_user

			self.session.add(user)
			self.session.commit()
			self.session.refresh(user)

		# Mark them as logged in.
		self._allow_user(user)

		# Redirect away.
		# TODO: Allow redirecting back to where you came from.
		self.redirect('/')

	@staticmethod
	def get_routes(configuration, called_name, options):
		configcopy = {}
		configcopy['called_name'] = called_name
		configcopy['options'] = options
		configcopy.update(configuration)
		routes = []
		routes.append(
			(
				r"/login/%s" % called_name,
				GoogleAuthController,
				configcopy
			)
		)
		return routes
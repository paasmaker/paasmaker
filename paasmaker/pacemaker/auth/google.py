
import paasmaker

from paasmaker.common.controller.base import BaseController

import colander
import tornado
import tornado.auth

# TODO: Add the ability to restrict login/account creation to certain
# domain names; eg your work domain name. This stops random user
# account creation, even though they'd have no permissions.

class GoogleAuthConfigurationSchema(colander.MappingSchema):
	# No options defined.
	pass

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
			GoogleAuthController.get_routes(route_extras, self.called_name)
		)

	def get_login_metadata(self):
		return {
			'uri': '/login/%s' % self.called_name,
			'text': 'Google',
			'image': None
		}

class GoogleAuthController(BaseController, tornado.auth.GoogleMixin):
	AUTH_METHODS = [BaseController.ANONYMOUS]

	def get(self):
		if self.get_argument("openid.mode", None):
			self.get_authenticated_user(self.async_callback(self._on_auth))
			return
		self.authenticate_redirect()

	@tornado.gen.engine
	def _on_auth(self, google_user):
		if not google_user:
			raise tornado.web.HTTPError(500, "Google auth failed")

		# The google_user dict has the following keys:
		# first_name
		# name
		# claimed_id
		# locale
		# last_name
		# email

		# Look up the user by email address.
		# TODO: Use the correct auth source name.
		user = self.session.query(
			paasmaker.model.User
		).filter(
			paasmaker.model.User.login==google_user['email'],
			paasmaker.model.User.auth_source=="paasmaker.auth.google"
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
	def get_routes(configuration, called_name):
		routes = []
		routes.append(
			(
				r"/login/%s" % called_name,
				GoogleAuthController,
				configuration
			)
		)
		return routes
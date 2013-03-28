#
# Paasmaker - Platform as a Service
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#

import paasmaker
from apirequest import APIRequest, APIResponse

class LoginAPIRequest(APIRequest):
	"""
	Requests a login from the system. The username and password
	are transmitted in clear text. Intended mainly for testing
	purposes.
	"""

	def set_credentials(self, username, password):
		"""
		Set the credentials for this request.

		:arg str username: The username.
		:arg str password: The clear text password.
		"""
		self.username = username
		self.password = password

	def build_payload(self):
		return {'username': self.username, 'password': self.password}

	def get_endpoint(self):
		return '/login'
#
# Paasmaker - Platform as a Service
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#

import colander
from base import BaseService, BaseServiceTest
import paasmaker

class ParametersServiceConfigurationSchema(colander.MappingSchema):
	# No options defined.
	pass

class ParametersServiceParametersSchema(colander.MappingSchema):
	# No parameter schema defined. We just accept whatever we're supplied.
	pass

# Parameters service.
class ParametersService(BaseService):
	"""
	This service simply returns, encoded, the parameters passed into it. Useful
	for testing or for pumping in configuration or values from the manifest.
	"""
	MODES = {
		paasmaker.util.plugin.MODE.SERVICE_CREATE: ParametersServiceParametersSchema(),
		paasmaker.util.plugin.MODE.SERVICE_DELETE: None
	}
	OPTIONS_SCHEMA = ParametersServiceConfigurationSchema()
	API_VERSION = "0.9.0"

	def create(self, name, callback, error_callback):
		# Does the same thing as update.
		self.logger.debug("Creating service with parameters: %s", str(self.raw_parameters))
		self.update(name, {}, callback, error_callback)

	def update(self, name, existing_credentials, callback, error_callback):
		"""
		Update the service (if required) returning new credentials. In many
		cases this won't make sense for a service, but is provided for a few
		services for which it does make sense.
		"""
		# We always succeed here, just passing back the options.
		self.logger.debug("Updating service with parameters: %s", str(self.raw_parameters))
		callback(self.raw_parameters, "Successfully modified service.")

	def remove(self, name, existing_credentials, callback, error_callback):
		"""
		Remove the service, using the options supplied by the application,
		and the credentials created when the service was created.
		"""
		callback("Successfully removed service.")

class ParametersServiceTest(BaseServiceTest):
	def test_simple(self):
		# There is very few ways this can go wrong,
		# but this is an example for other services.
		self.registry.register(
			'paasmaker.service.parameters',
			'paasmaker.pacemaker.service.parameters.ParametersService',
			{},
			'Parameters Service'
		)
		service = self.registry.instantiate(
			'paasmaker.service.parameters',
			paasmaker.util.plugin.MODE.SERVICE_CREATE,
			{'test': 'bar'}
		)

		service.create('test', self.success_callback, self.failure_callback)

		self.wait()

		self.assertTrue(self.success, "Service creation was not successful.")
		self.assertEquals(len(self.credentials), 1, "Service did not return expected number of keys.")
		self.assertEquals(self.credentials['test'], 'bar', "Service did not return expected values.")
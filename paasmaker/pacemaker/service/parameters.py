
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
	MODES = [paasmaker.util.plugin.MODE.SERVICE_CREATE]
	OPTIONS_SCHEMA = ParametersServiceConfigurationSchema()
	PARAMETERS_SCHEMA = {paasmaker.util.plugin.MODE.SERVICE_CREATE: ParametersServiceParametersSchema()}

	def create(self, callback, error_callback):
		# Does the same thing as update.
		self.logger.debug("Creating service with parameters: %s", str(self.raw_parameters))
		self.update(callback, error_callback)

	def update(self, callback, error_callback):
		"""
		Update the service (if required) returning new credentials. In many
		cases this won't make sense for a service, but is provided for a few
		services for which it does make sense.
		"""
		# We always succeed here, just passing back the options.
		self.logger.debug("Updating service with parameters: %s", str(self.raw_parameters))
		callback(self.raw_parameters, "Successfully modified service.")

	def remove(self, callback, error_callback):
		"""
		Remove the service, using the options supplied by the application,
		and the credentials created when the service was created.
		"""
		callback("Successfully removed service.")

class ParametersServiceTest(BaseServiceTest):
	def test_simple(self):
		# There is very few ways this can go wrong,
		# but this is an example for other services.
		service = ParametersService(self.configuration, paasmaker.util.plugin.MODE.SERVICE_CREATE, {}, {'test': 'bar'})

		# Sanity check.
		service.check_options()
		service.check_parameters(paasmaker.util.plugin.MODE.SERVICE_CREATE)

		service.create(self.success_callback, self.failure_callback)

		self.wait()

		self.assertTrue(self.success, "Service creation was not successful.")
		self.assertEquals(len(self.credentials), 1, "Service did not return expected number of keys.")
		self.assertEquals(self.credentials['test'], 'bar', "Service did not return expected values.")
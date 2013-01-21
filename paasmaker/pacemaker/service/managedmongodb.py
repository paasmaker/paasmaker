
import os
import glob

from base import BaseService, BaseServiceTest
import paasmaker

import colander

class ManagedMongoServiceConfigurationSchema(colander.MappingSchema):
	min_port = colander.SchemaNode(colander.Integer(),
		title="Minimum port",
		description="The minimum port to allocate mongoDB instances in.",
		default=42700,
		missing=42700)
	max_port = colander.SchemaNode(colander.Integer(),
		title="Maximum port",
		description="The maximum port to allocate mongoDB instances in.",
		default=42799,
		missing=42799)
	apply_passwords = colander.SchemaNode(colander.Boolean(),
		title="Apply Passwords",
		description="If true, set a password on the mongoDB instance. It will be supplied to the application.",
		default=True,
		missing=True)
	shutdown = colander.SchemaNode(colander.Boolean(),
		title="Shutdown",
		description="If true, shut down all managed mongoDB instances when the node stops. You won't want to do this normally.",
		default=False,
		missing=False)

class ManagedMongoServiceParametersSchema(colander.MappingSchema):
	# No options available for runtime configuration.
	pass

class ManagedMongoService(BaseService):
	MODES = {
		paasmaker.util.plugin.MODE.SERVICE_CREATE: ManagedMongoServiceParametersSchema(),
		paasmaker.util.plugin.MODE.STARTUP_ASYNC_PRELISTEN: None,
		paasmaker.util.plugin.MODE.SHUTDOWN_POSTNOTIFY: None
	}
	OPTIONS_SCHEMA = ManagedMongoServiceConfigurationSchema()

	def create(self, name, callback, error_callback):
		instance_name = self._safe_name(name)
		if self.options['apply_passwords']:
			password = None
			#password = self._generate_password()
		else:
			password = None

		# Create or activate our instance.
		instance_path = self.configuration.get_scratch_path_exists(
			self.called_name,
			instance_name
		)

		manager = paasmaker.util.managedmongodb.ManagedMongo(self.configuration)
		try:
			# TODO: This shouldn't exist yet, because we're creating it...
			# Decide how to handle this case.
			manager.load_parameters(instance_path)

			port = manager.get_port()

			self.logger.info("Using existing instance on port %d.", port)

		except paasmaker.util.ManagedDaemonError, ex:
			portfinder = paasmaker.util.port.FreePortFinder()
			port = portfinder.free_in_range(
				self.options['min_port'],
				self.options['max_port']
			)

			self.logger.info("Creating new instance on port %d.", port)

			# Doesn't yet exist. Create it.
			manager.configure(
				instance_path,
				port,
				'0.0.0.0',
				password
			)

		def on_running(message):
			# Success! Emit the credentials.
			self.logger.info("Successfully started. Returning the credentials.")
			credentials = {}
			credentials['protocol'] = 'mongodb'
			credentials['hostname'] = self.configuration.get_flat('my_route')
			credentials['port'] = port
			if password:
				credentials['password'] = password
			callback(credentials, "Successfully created mongoDB instance.")

		def on_startup_failure(message, exception=None):
			self.logger.error(message)
			if exception:
				self.logger.error("Exception:", exc_info=exception)

			error_callback(message, exception)

		manager.start_if_not_running(on_running, on_startup_failure)

	def update(self, name, existing_credentials, callback, error_callback):
		# No action to take here.
		callback(existing_credentials, "Successfully modified service.")

	def remove(self, name, existing_credentials, callback, error_callback):
		# TODO: Implement.
		error_callback("Removing not implemented.")

	def startup_async_prelisten(self, callback, error_callback):
		# Start up all our managed instances, if they're not already listening.
		instance_root = self.configuration.get_scratch_path_exists(
			self.called_name
		)

		paths = glob.glob(os.path.join(instance_root, '*'))

		def process_path(message):
			try:
				instance_path = paths.pop()

				try:
					manager = paasmaker.util.managedmongodb.ManagedMongo(self.configuration)
					manager.load_parameters(instance_path)
					self.logger.info("Found managed mongoDB at path %s - starting.", instance_path)

					# Start it up.
					# If it fails, call the error callback.
					# When it succeeds, proceed.
					manager.start_if_not_running(process_path, error_callback)

				except paasmaker.util.ManagedDaemonError, ex:
					# Just move on to the next one.
					self.logger.error("Path %s doesn't have a managed mongoDB instance - skipping.")

			except IndexError, ex:
				# That's it, that was the last one.
				callback("All managed instances started.")

		# Kick off the process.
		process_path('')

	def shutdown_postnotify(self, callback, error_callback):
		if self.options['shutdown']:
			instance_root = self.configuration.get_scratch_path_exists(
				self.called_name
			)

			paths = glob.glob(os.path.join(instance_root, '*'))

			def process_path(message):
				try:
					instance_path = paths.pop()

					try:
						manager = paasmaker.util.managedmongodb.ManagedMongo(self.configuration)
						manager.load_parameters(instance_path)
						self.logger.info("Found managed mongoDB at path %s - shutting down", instance_path)

						# Shut it down.
						manager.stop()

						# Move onto the next one.
						process_path("Completed.")

					except paasmaker.util.ManagedDaemonError, ex:
						# Just move on to the next one.
						self.logger.error("Path %s doesn't have a managed mongoDB instance - skipping.")

				except IndexError, ex:
					# That's it, that was the last one.
					callback("All managed instances stopped.")

			# Kick off the process.
			process_path('')
		else:
			callback("No action to perform.")

class ManagedMongoServiceTest(BaseServiceTest):
	def test_simple(self):
		self.registry.register(
			'paasmaker.service.managedmongodb',
			'paasmaker.pacemaker.service.managedmongodb.ManagedMongoService',
			{
				'shutdown': True
			},
			'Managed mongoDB Service'
		)
		service = self.registry.instantiate(
			'paasmaker.service.managedmongodb',
			paasmaker.util.plugin.MODE.SERVICE_CREATE,
			{}
		)

		service.create('test', self.success_callback, self.failure_callback)

		self.wait()

		self.assertTrue(self.success, "Service creation was not successful.")
		self.assertEquals(len(self.credentials), 4, "Service did not return expected number of keys.")

		client = tornadoredis.Client(
			host=self.credentials['hostname'],
			port=self.credentials['port'],
			password=self.credentials['password'],
			io_loop=self.io_loop
		)
		client.connect()

		client.set('test', 'bar', callback=self.stop)
		self.wait()
		client.get('test', callback=self.stop)
		result = self.wait()

		self.assertEquals(result, 'bar', "Result was not as expected.")

		client.disconnect()

		# Now, shut down the instances.
		service.shutdown_postnotify(self.stop, self.stop)
		self.wait()

		# Wait for it to be free.
		self.short_wait_hack(length=0.5)

		# The port should now be free.
		self.assertFalse(self.configuration.port_allocator.in_use(self.credentials['port']), "Port was not free.")

		# Now start them back up again.
		service.startup_async_prelisten(self.stop, self.stop)
		self.wait()

		# Try to connect again. This should work.
		client = tornadoredis.Client(
			host=self.credentials['hostname'],
			port=self.credentials['port'],
			password=self.credentials['password'],
			io_loop=self.io_loop
		)
		client.connect()

		client.get('test', callback=self.stop)
		result = self.wait()

		self.assertEquals(result, 'bar', "Result was not as expected.")
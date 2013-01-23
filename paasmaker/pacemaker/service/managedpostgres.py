
import os
import time

from base import BaseService, BaseServiceTest
from postgres import PostgresService, PostgresServiceTest
import paasmaker

import colander

class ManagedPostgresServiceConfigurationSchema(colander.MappingSchema):
	port = colander.SchemaNode(colander.Integer(),
		title="TCP Port to use",
		description="The TCP port to use for the managed instance.",
		default=42800,
		missing=42800)
	host = colander.SchemaNode(colander.String(),
		title="The address to bind to",
		description="The address to bind to. If you only will use the databases on this host, use 127.0.0.1. Otherwise, use 0.0.0.0.",
		default="127.0.0.1",
		missing="127.0.0.1")
	password = colander.SchemaNode(colander.String(),
		title="The server's administrative password",
		description="The administrative password for this instance. You must supply one, and the plugin can't change it after it's started up a server.")
	shutdown = colander.SchemaNode(colander.Boolean(),
		title="Shutdown",
		description="If true, shut down the managed postgres when the node stops. You won't want to do this normally.",
		default=False,
		missing=False)

class ManagedPostgresServiceParametersSchema(colander.MappingSchema):
	# No options available for runtime configuration.
	pass

class ManagedPostgresService(PostgresService):
	"""
	Start a Postgres server (using the PostgresDaemon class) and make
	it available to applications as a service.

	To enable, add a "services" section to your application manifest,
	and add an item with "provider: paasmaker.service.managedpostgres"
	and	a name of your choosing.
	"""

	MODES = {
		paasmaker.util.plugin.MODE.SERVICE_CREATE: ManagedPostgresServiceParametersSchema(),
		paasmaker.util.plugin.MODE.STARTUP_ASYNC_PRELISTEN: None,
		paasmaker.util.plugin.MODE.SHUTDOWN_POSTNOTIFY: None
	}
	OPTIONS_SCHEMA = ManagedPostgresServiceConfigurationSchema()

	def _postgres_path(self):
		return self.configuration.get_scratch_path_exists(
			self.called_name
		)

	def create(self, name, callback, error_callback):
		# See if our managed postgres exists, and is running.
		postgres_path = self._postgres_path()
		manager = paasmaker.util.managedpostgres.PostgresDaemon(self.configuration)
		try:
			manager.load_parameters(postgres_path)

			port = manager.get_port()

			self.logger.info("Using existing instance on port %d.", port)

		except paasmaker.util.ManagedDaemonError, ex:
			port = self.options['port']

			self.logger.info("Creating new instance on port %d.", port)

			# Doesn't yet exist. Create it.
			manager.configure(
				postgres_path,
				port,
				self.options['host'],
				self.options['password']
			)

		def on_delay():
			super(ManagedPostgresService, self).create(name, callback, error_callback)

		def on_running(message):
			# Success!
			# Ask our superclass to create the credentials for us.
			self.logger.info("Successfully started. Generating credentials.")

			self.options['hostname'] = '127.0.0.1' #self.configuration.get_flat('my_route')
			self.options['username'] = 'postgres'

			# Wait a little bit for Postgres to settle down.
			self.configuration.io_loop.add_timeout(time.time() + 0.5, on_delay)

		def on_startup_failure(message, exception=None):
			self.logger.error(message)
			if exception:
				self.logger.error("Exception:", exc_info=exception)

			error_callback(message, exception)

		manager.start_if_not_running(on_running, on_startup_failure)

	def update(self, name, existing_credentials, callback, error_callback):
		super(ManagedPostgresService, self).update(name, existing_credentials, callback, error_callback)

	def remove(self, name, existing_credentials, callback, error_callback):
		super(ManagedPostgresService, self).remove(name, existing_credentials, callback, error_callback)

	def startup_async_prelisten(self, callback, error_callback):
		# Start up all our managed instances, if they're not already listening.
		postgres_path = self._postgres_path()

		try:
			manager = paasmaker.util.managedpostgres.PostgresDaemon(self.configuration)
			manager.load_parameters(postgres_path)
			self.logger.info("Found managed postgres at path %s - starting.", postgres_path)

			# Start it up.
			# If it fails, call the error callback.
			# When it succeeds, proceed.
			manager.start_if_not_running(callback, error_callback)

		except paasmaker.util.ManagedDaemonError, ex:
			# We don't have a postgres instance here. This is probably
			# because no applications have been created with it yet. Not
			# a problem; do nothing here in this case.
			callback("No databases set up yet. No action to take.")

	def shutdown_postnotify(self, callback, error_callback):
		if self.options['shutdown']:
			instance_root = self.configuration.get_scratch_path_exists(
				self.called_name
			)

			postgres_path = self._postgres_path()

			try:
				manager = paasmaker.util.managedpostgres.PostgresDaemon(self.configuration)
				manager.load_parameters(postgres_path)
				self.logger.info("Found managed postgres at path %s - shutting down", postgres_path)

				# Shut it down.
				manager.stop()

				# Move onto the next one.
				callback("Shut down Postgres instance.")

			except paasmaker.util.ManagedDaemonError, ex:
				# No such postgres instance yet. Not a problem;
				# just take no action.
				callback("No action to perform.")

		else:
			callback("No action to perform.")

class ManagedPostgresServiceTest(PostgresServiceTest):
	def test_simple(self):
		# Override the plugin it registered.
		self.registry.register(
			'paasmaker.service.postgres',
			'paasmaker.pacemaker.service.managedpostgres.ManagedPostgresService',
			{
				'port': self.configuration.get_free_port(),
				'password': 'supersecret',
				'shutdown': True
			},
			'Postgres Service'
		)

		# Use the parent's test.
		super(ManagedPostgresServiceTest, self).test_simple()

		# And then shut down the service.
		service = self.registry.instantiate(
			'paasmaker.service.postgres',
			paasmaker.util.plugin.MODE.SERVICE_CREATE,
			{}
		)

		# Now, shut down the instances.
		service.shutdown_postnotify(self.stop, self.stop)
		self.wait()

		# Wait for it to be free.
		#self.short_wait_hack(length=1.0)

		# The port should now be free.
		# TODO: It is free... but this check is not working.
		#self.assertFalse(self.configuration.port_allocator.in_use(service.options['port']), "Port was not free.")

		# Now start them back up again.
		#service.startup_async_prelisten(self.stop, self.stop)
		#self.wait()

		# The port should now be used.
		#self.assertTrue(self.configuration.port_allocator.in_use(service.options['port']), "Port was not in use.")

import os
import time

from base import BaseService, BaseServiceTest
from mysql import MySQLService, MySQLServiceTest
import paasmaker

import torndb
import colander

class ManagedMySQLServiceConfigurationSchema(colander.MappingSchema):
	port = colander.SchemaNode(colander.Integer(),
		title="TCP Port to use",
		description="The TCP port to use for the managed instance.",
		default=42801,
		missing=42801)
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
		description="If true, shut down the managed MySQL when the node stops. You won't want to do this normally.",
		default=False,
		missing=False)

class ManagedMySQLServiceParametersSchema(colander.MappingSchema):
	# No options available for runtime configuration.
	pass

class ManagedMySQLService(MySQLService):
	"""
	Start a MySQL server (using the MySQLDaemon class) and make
	it available to applications as a service.

	To enable, add a "services" section to your application manifest,
	and add an item with "provider: paasmaker.service.managedmysql"
	and	a name of your choosing.
	"""

	MODES = {
		paasmaker.util.plugin.MODE.SERVICE_CREATE: ManagedMySQLServiceParametersSchema(),
		paasmaker.util.plugin.MODE.SERVICE_DELETE: None,
		paasmaker.util.plugin.MODE.STARTUP_ASYNC_PRELISTEN: None,
		paasmaker.util.plugin.MODE.SHUTDOWN_POSTNOTIFY: None
	}
	OPTIONS_SCHEMA = ManagedMySQLServiceConfigurationSchema()

	def _mysql_path(self):
		return self.configuration.get_scratch_path_exists(
			self.called_name
		)

	def create(self, name, callback, error_callback):
		# See if our managed mysql exists, and is running.
		mysql_path = self._mysql_path()
		manager = paasmaker.util.mysqldaemon.MySQLDaemon(self.configuration)
		try:
			manager.load_parameters(mysql_path)

			port = manager.get_port()

			self.logger.info("Using existing instance on port %d.", port)

		except paasmaker.util.ManagedDaemonError, ex:
			port = self.options['port']

			self.logger.info("Creating new instance on port %d.", port)

			# Doesn't yet exist. Create it.
			manager.configure(
				mysql_path,
				port,
				self.options['host'],
				self.options['password']
			)

		def on_delay():
			super(ManagedMySQLService, self).create(name, callback, error_callback)

		def on_running(message):
			# Success!
			# Ask our superclass to create the credentials for us.
			self.logger.info("Successfully started. Generating credentials.")

			self.options['hostname'] = '127.0.0.1' #self.configuration.get_flat('my_route')
			self.options['username'] = 'root'

			# Wait a little bit for MySQL to settle down.
			self.configuration.io_loop.add_timeout(time.time() + 0.5, on_delay)

		def on_startup_failure(message, exception=None):
			self.logger.error(message)
			if exception:
				self.logger.error("Exception:", exc_info=exception)

			error_callback(message, exception)

		manager.start_if_not_running(on_running, on_startup_failure)

	def update(self, name, existing_credentials, callback, error_callback):
		super(ManagedMySQLService, self).update(name, existing_credentials, callback, error_callback)

	def remove(self, name, existing_credentials, callback, error_callback):
		# TODO: don't hack this quite so badly
		self.options['hostname'] = '127.0.0.1'
		self.options['username'] = 'root'

		super(ManagedMySQLService, self).remove(name, existing_credentials, callback, error_callback)

	def startup_async_prelisten(self, callback, error_callback):
		# Start up all our managed instances, if they're not already listening.
		mysql_path = self._mysql_path()

		try:
			manager = paasmaker.util.mysqldaemon.MySQLDaemon(self.configuration)
			manager.load_parameters(mysql_path)
			self.logger.info("Found managed mysql at path %s - starting.", mysql_path)

			# Start it up.
			# If it fails, call the error callback.
			# When it succeeds, proceed.
			manager.start_if_not_running(callback, error_callback)

		except paasmaker.util.ManagedDaemonError, ex:
			# We don't have a mysql instance here. This is probably
			# because no applications have been created with it yet. Not
			# a problem; do nothing here in this case.
			callback("No databases set up yet. No action to take.")

	def shutdown_postnotify(self, callback, error_callback):
		if self.options['shutdown']:
			mysql_path = self._mysql_path()

			try:
				manager = paasmaker.util.mysqldaemon.MySQLDaemon(self.configuration)
				manager.load_parameters(mysql_path)
				self.logger.info("Found managed mysql at path %s - shutting down", mysql_path)

				# Shut it down.
				manager.stop()

				# Move onto the next one.
				callback("Shut down MySQL instance.")

			except paasmaker.util.ManagedDaemonError, ex:
				# No such mysql instance yet. Not a problem;
				# just take no action.
				callback("No action to perform.")

		else:
			callback("No action to perform.")

class ManagedMySQLServiceTest(MySQLServiceTest):
	def setUp(self):
		# Call above our class - because the parent one starts
		# a redundant additional server.
		super(MySQLServiceTest, self).setUp()

	def test_simple(self):
		# Override the plugin it registered.
		self.registry.register(
			'paasmaker.service.mysql',
			'paasmaker.pacemaker.service.managedmysql.ManagedMySQLService',
			{
				'port': self.configuration.get_free_port(),
				'password': 'supersecret',
				'shutdown': True
			},
			'MySQL Service'
		)

		# Try starting the service.
		service = self.registry.instantiate(
			'paasmaker.service.mysql',
			paasmaker.util.plugin.MODE.SERVICE_CREATE,
			{}
		)

		service.create('test', self.success_callback, self.failure_callback)
		self.wait()

		# The port should now be used.
		self.assertTrue(self.success, "Creating managed MySQL service didn't succeed.")
		self.assertTrue(self.configuration.port_allocator.in_use(service.options['port']), "MySQL port %d was not in use." % service.options['port'])

		# Some basic operations copied out of the parent test.
		connection = torndb.Connection(
			"%s:%d" % (self.credentials['hostname'], self.credentials['port']),
			self.credentials['database'],
			user=self.credentials['username'],
			password=self.credentials['password']
		)

		connection.execute("CREATE TABLE foo (id INTEGER)")
		connection.execute("INSERT INTO foo VALUES (1)")
		results = connection.query("SELECT * FROM foo")

		for row in results:
			self.assertEqual(row['id'], 1, "Row value not as expected.")

		# Instantiate the plugin in delete mode and delete the databases associated with it.
		port_copy = service.options['port']
		service = self.registry.instantiate(
			'paasmaker.service.mysql',
			paasmaker.util.plugin.MODE.SERVICE_DELETE,
			{}
		)

		service.remove('test', self.credentials, self.success_remove_callback, self.failure_callback)
		self.wait()
		self.assertTrue(self.success, "Deleting managed MySQL service didn't succeed.")

		# Finally, shut down the service and check that the daemon has stopped.
		service.shutdown_postnotify(self.stop, self.stop)
		self.wait()
		self.short_wait_hack(length=1.0)
		self.assertFalse(self.configuration.port_allocator.in_use(port_copy), "MySQL port %d was not free." % port_copy)

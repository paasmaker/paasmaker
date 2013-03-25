
from base import BaseService, BaseServiceTest
import paasmaker

import torndb
import MySQLdb
import colander

class MySQLServiceConfigurationSchema(colander.MappingSchema):
	hostname = colander.SchemaNode(colander.String(),
		title="MySQL server hostname",
		description="The MySQL server hostname - used to create the database and then supplied to the application as is.")
	port = colander.SchemaNode(colander.Integer(),
		title="MySQL server port",
		description="The port that the MySQL server is listening on.",
		default=3306,
		missing=3306)
	username = colander.SchemaNode(colander.String(),
		title="MySQL Administrative username",
		description="A MySQL user that can create users and databases.")
	password = colander.SchemaNode(colander.String(),
		title="MySQL Administrative password",
		description="The password for the user.")

class MySQLServiceParametersSchema(colander.MappingSchema):
	# No parameters required. Plugins just ask for a database.
	pass

def administrative_connection_helper(options):
	connection = torndb.Connection(
		"%s:%d" % (options['hostname'], options['port']),
		'mysql', # TODO: Select a different database.
		user=options['username'],
		password=options['password']
	)

	return connection

class ThreadedMySQLDatabaseCreator(paasmaker.util.threadcallback.ThreadCallback):
	"""
	Helper class to do the sync MySQL work on a thread, to avoid it locking up
	the Tornado process.
	"""

	def _work(self, options, username, database, password):
		connection = administrative_connection_helper(options)

		# Create the user.
		connection.execute(
			"CREATE USER %s@'%%' IDENTIFIED BY %s",
			username,
			password
		)

		# Create the database.
		# NOTE: The database name is already made safe (alfanum only)
		# so it can be inserted into this query directly.
		# TODO: Double check all this.
		connection.execute(
			"CREATE DATABASE %s" % database
		)

		# Grant the user all permissions on that database.
		# NOTE: The username/database name are already database
		# safe, so it can be inserted into the query directly.
		# TODO: Double check all this.
		connection.execute(
			"GRANT ALL ON %s.* TO '%s'@'%%%%' IDENTIFIED BY %%s" % (database, username),
			password
		)
		# TODO: NOTE: We're doing this twice, because MySQL somehow doesn't allow us
		# to connect locally without the second record. It's a MySQL quirk.
		connection.execute(
			"GRANT ALL ON %s.* TO '%s'@'localhost' IDENTIFIED BY %%s" % (database, username),
			password
		)

		self._callback("Completed successfully.")

class ThreadedMySQLDatabaseDeletor(paasmaker.util.threadcallback.ThreadCallback):
	"""
	Helper class to do the sync MySQL work on a thread, to avoid it locking up
	the Tornado process.
	"""

	def _work(self, options, existing_credentials):
		connection = administrative_connection_helper(options)

		# TODO: These values should be safe to insert back into the query directly,
		# however, they may not be. Fix this.
		connection.execute("DROP DATABASE %s" % existing_credentials['database'])
		connection.execute("DROP USER %s" % existing_credentials['username'])

		self._callback("Completed successfully.")

# MySQL service.
class MySQLService(BaseService):
	MODES = {
		paasmaker.util.plugin.MODE.SERVICE_CREATE: MySQLServiceParametersSchema(),
		paasmaker.util.plugin.MODE.SERVICE_DELETE: None
	}
	OPTIONS_SCHEMA = MySQLServiceConfigurationSchema()
	API_VERSION = "0.9.0"

	def create(self, name, callback, error_callback):
		# Choose a username, password, and database name.
		# The username and database name are based off the supplied name.
		username = self._safe_name(name, max_length=16)
		database = username
		password = self._generate_password()

		self.logger.info("Chosen username/database name %s", username)

		def completed_database(message):
			callback(
				{
					'protocol': 'mysql',
					'hostname': self.options['hostname'],
					'username': username,
					'database': database,
					'password': password,
					'port': self.options['port']
				},
				"Successfully created database."
			)

		maker = ThreadedMySQLDatabaseCreator(self.configuration.io_loop, completed_database, error_callback)
		maker.work(self.options, username, database, password)

	def update(self, name, existing_credentials, callback, error_callback):
		# No action to take here.
		callback(existing_credentials, "Successfully modified service.")

	def remove(self, name, existing_credentials, callback, error_callback):
		# Remove the database.
		self.logger.info("Dropping database %s", existing_credentials['database'])

		def completed_deleting(message):
			self.logger.info("Completed.")
			callback("Removed successfully.")

		maker = ThreadedMySQLDatabaseDeletor(self.configuration.io_loop, completed_deleting, error_callback)
		maker.work(self.options, existing_credentials)

class MySQLServiceTest(BaseServiceTest):
	def setUp(self):
		super(MySQLServiceTest, self).setUp()

		self.server = paasmaker.util.mysqldaemon.MySQLDaemon(self.configuration)
		self.server.configure(
			self.configuration.get_scratch_path_exists('mysql'),
			self.configuration.get_free_port(),
			'127.0.0.1',
			password="test"
		)
		self.server.start(self.stop, self.stop)
		result = self.wait()

		self.registry.register(
			'paasmaker.service.mysql',
			'paasmaker.pacemaker.service.mysql.MySQLService',
			{
				'hostname': '127.0.0.1',
				'port': self.server.get_port(),
				'username': 'root',
				'password': 'test'
			},
			'MySQL Service'
		)

	def tearDown(self):
		if hasattr(self, 'server'):
			self.server.destroy()

		super(MySQLServiceTest, self).tearDown()

	def test_simple(self):
		service = self.registry.instantiate(
			'paasmaker.service.mysql',
			paasmaker.util.plugin.MODE.SERVICE_CREATE,
			{}
		)

		service.create('testlongname', self.success_callback, self.failure_callback)

		self.wait()

		self.assertTrue(self.success, "Service creation was not successful.")
		self.assertEquals(len(self.credentials), 6, "Service did not return expected number of keys.")

		credentials = self.credentials

		#delay = raw_input("Press enter to proceed.")

		# Try to connect with the supplied credentials.
		connection = torndb.Connection(
			"%s:%d" % (credentials['hostname'], credentials['port']),
			credentials['database'],
			user=credentials['username'],
			password=credentials['password']
		)

		connection.execute("CREATE TABLE foo (id INTEGER)")
		connection.execute("INSERT INTO foo VALUES (1)")
		results = connection.query("SELECT * FROM foo")

		for row in results:
			self.assertEqual(row['id'], 1, "Row value not as expected.")

		# Now remove the database.
		service.remove('testlongname', credentials, self.success_remove_callback, self.failure_callback)

		self.assertTrue(self.success, "Service deletion was not successful.")

		# Try to connect with the supplied credentials.
		# This should fail.
		# TODO: Fix this - torndb "eats" the exception and logs it,
		# but doesn't raise it.
		# try:
		# 	connection = torndb.Connection(
		# 		"%s:%d" % (credentials['hostname'], credentials['port']),
		# 		credentials['database'],
		# 		user=credentials['username'],
		# 		password=credentials['password']
		# 	)

		# 	self.assertTrue(False, "Should have thrown exception.")
		# except MySQLdb.OperationalError, ex:
		# 	self.assertTrue(True, "Threw correct exception.")
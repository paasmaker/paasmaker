
from base import BaseService, BaseServiceTest
import paasmaker

import torndb
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

# MySQL service.
class MySQLService(BaseService):
	MODES = {
		paasmaker.util.plugin.MODE.SERVICE_CREATE: MySQLServiceParametersSchema()
	}
	OPTIONS_SCHEMA = MySQLServiceConfigurationSchema()

	def create(self, name, callback, error_callback):
		# Choose a username, password, and database name.
		# The username and database name are based off the supplied name.
		username = self._safe_name(name)
		database = username
		password = self._generate_password()

		self.logger.info("Chosen username/database name %s", username)

		# TODO: None of this is async. It better not take long.
		connection = torndb.Connection(
			"%s:%d" % (self.options['hostname'], self.options['port']),
			'mysql', # TODO: Select a different database.
			user=self.options['username'],
			password=self.options['password']
		)

		# Create the user.
		connection.execute(
			"CREATE USER %s IDENTIFIED BY %s",
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


	def update(self, name, existing_credentials, callback, error_callback):
		# No action to take here.
		callback(existing_credentials, "Successfully modified service.")

	def remove(self, name, existing_credentials, callback, error_callback):
		error_callback("Removing not implemented.")

class MySQLServiceTest(BaseServiceTest):
	def setUp(self):
		self.skipTest("Not yet working.")

		super(MySQLServiceTest, self).setUp()

		self.server = paasmaker.util.managedmysql.ManagedMySQL(self.configuration)
		self.server.configure(
			self.configuration.get_scratch_path_exists('mysql'),
			self.configuration.get_free_port(),
			'127.0.0.1',
			password="test"
		)
		self.server.start(self.stop, self.stop)
		result = self.wait()

	def tearDown(self):
		self.server.destroy()

		super(MySQLServiceTest, self).tearDown()

	def test_simple(self):
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
		service = self.registry.instantiate(
			'paasmaker.service.mysql',
			paasmaker.util.plugin.MODE.SERVICE_CREATE,
			{}
		)

		service.create('test', self.success_callback, self.failure_callback)

		self.wait()

		#print str(self.credentials)
		self.assertTrue(self.success, "Service creation was not successful.")
		self.assertEquals(len(self.credentials), 5, "Service did not return expected number of keys.")

		#delay = raw_input("Press enter to proceed.")

		# Try to connect with the supplied credentials.
		connection = torndb.Connection(
			"%s:%d" % (self.credentials['hostname'], self.credentials['port']),
			self.credentials['database'],
			user=self.credentials['username'],
			password=self.credentials['password']
		)

		connection.query("SHOW TABLES")
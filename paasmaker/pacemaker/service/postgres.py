
from base import BaseService, BaseServiceTest
import paasmaker

import momoko
import psycopg2
import colander

class PostgresServiceConfigurationSchema(colander.MappingSchema):
	hostname = colander.SchemaNode(colander.String(),
		title="Postgres server hostname",
		description="The Postgres server hostname - used to create the database and then supplied to the application as is.")
	port = colander.SchemaNode(colander.Integer(),
		title="Postgres server port",
		description="The port that the Postgres server is listening on.",
		default=5432,
		missing=5432)
	username = colander.SchemaNode(colander.String(),
		title="Postgres Administrative username",
		description="A Postgres user that can create users and databases.")
	password = colander.SchemaNode(colander.String(),
		title="Postgres Administrative password",
		description="The password for the user.")

class PostgresServiceParametersSchema(colander.MappingSchema):
	# No parameters required. Plugins just ask for a database.
	pass

class PostgresService(BaseService):
	MODES = {
		paasmaker.util.plugin.MODE.SERVICE_CREATE: PostgresServiceParametersSchema()
	}
	OPTIONS_SCHEMA = PostgresServiceConfigurationSchema()
	API_VERSION = "0.9.0"

	def create(self, name, callback, error_callback):
		# Choose a username, password, and database name.
		# The username and database name are based off the supplied name.
		username = self._safe_name(name)
		database = username
		password = self._generate_password()

		self.logger.info("Chosen username/database name %s", username)

		def on_database_created(result):
			# Done!
			self.db.close()
			self.logger.info("Completed creating database.")
			callback(
				{
					'protocol': 'pgsql',
					'hostname': self.options['hostname'],
					'username': username,
					'database': database,
					'password': password,
					'port': self.options['port']
				},
				"Successfully created database."
			)

		def on_user_created(result):
			self.logger.info("Creating database...")
			# NOTE: Database and username are already safe for database
			# use so is inserted directly into the query.
			# TODO: Verify this.
			self.db.execute(
				"CREATE DATABASE %s OWNER %s" %	(database, username),
				callback=on_database_created
			)

		def on_connected():
			# NOTE: Username is already safe for database
			# use so is inserted directly into the query.
			# TODO: Verify this.
			self.logger.info("Creating user...")
			self.db.execute(
				"CREATE USER %s PASSWORD %%s" % username,
				(password,),
				callback=on_user_created
			)

		self.db = self._get_database()

		on_connected()

	def update(self, name, existing_credentials, callback, error_callback):
		# No action to take here.
		callback(existing_credentials, "Successfully modified service.")

	def remove(self, name, existing_credentials, callback, error_callback):
		# Delete the database, removing all data along with it.
		def on_user_dropped(result):
			# Done!
			self.db.close()
			self.logger.info("Completed deleting resources.")
			callback("Completed deleting resources.")

		def on_database_deleted(result):
			self.logger.info("Deleting user...")
			# NOTE: Username are already safe for database
			# use so is inserted directly into the query.
			# TODO: Verify this.
			self.db.execute(
				"DROP USER %s" % existing_credentials['username'],
				callback=on_user_dropped
			)

		def on_connected():
			# NOTE: 'Database' is already safe for database
			# use so is inserted directly into the query.
			# TODO: Verify this.
			self.logger.info("Deleting database...")
			self.db.execute(
				"DROP DATABASE %s" % existing_credentials['database'],
				callback=on_database_deleted
			)

		self.db = self._get_database()

		on_connected()

	def _get_database(self):
		return momoko.AsyncClient(
			{
				'host': self.options['hostname'],
				'port': self.options['port'],
				'user': self.options['username'],
				'password': self.options['password'],
				'ioloop': self.configuration.io_loop
			}
		)

class PostgresServiceTest(BaseServiceTest):
	def setUp(self):
		super(PostgresServiceTest, self).setUp()

		self.server = paasmaker.util.postgresdaemon.PostgresDaemon(self.configuration)
		self.server.configure(
			self.configuration.get_scratch_path_exists('postgres'),
			'/usr/lib/postgresql/9.1/bin', # TODO: Ubuntu Specific.
			self.configuration.get_free_port(),
			'127.0.0.1',
			password="test"
		)
		self.server.start(self.stop, self.stop)
		result = self.wait()

		# Give the database a short time to settle down.
		self.short_wait_hack(length=0.5)
		#delay = raw_input("Press enter to continue.")

		self.registry.register(
			'paasmaker.service.postgres',
			'paasmaker.pacemaker.service.postgres.PostgresService',
			{
				'hostname': '127.0.0.1',
				'port': self.server.get_port(),
				'username': 'postgres',
				'password': 'test'
			},
			'Postgres Service'
		)

	def tearDown(self):
		if hasattr(self, 'server'):
			self.server.destroy()

		super(PostgresServiceTest, self).tearDown()

	def test_simple(self):
		service = self.registry.instantiate(
			'paasmaker.service.postgres',
			paasmaker.util.plugin.MODE.SERVICE_CREATE,
			{}
		)

		service.create('test', self.success_callback, self.failure_callback)

		self.wait()

		#print str(self.credentials)
		self.assertTrue(self.success, "Service creation was not successful.")
		self.assertEquals(len(self.credentials), 6, "Service did not return expected number of keys.")

		#delay = raw_input("Press enter to proceed.")

		# Connect to the database and execute a query.
		db = momoko.AsyncClient(
			{
				'host': self.credentials['hostname'],
				'port': self.credentials['port'],
				'user': self.credentials['username'],
				'password': self.credentials['password'],
				'ioloop': self.configuration.io_loop
			}
		)

		db.execute("CREATE TABLE foo (id integer)", callback=self.stop)
		result = self.wait()
		db.execute("INSERT INTO foo VALUES (1)", callback=self.stop)
		result = self.wait()
		db.execute("SELECT id FROM foo", callback=self.stop)
		result = self.wait()

		for row in result:
			self.assertEquals(row[0], 1, "Result was not as expected.")

		db.close()

		credentials_copy = self.credentials

		# Now attempt to delete the service.
		service.remove('test', self.credentials, self.success_remove_callback, self.failure_callback)
		self.wait()

		self.assertTrue(self.success, "Did not succeed.")

		self.credentials = credentials_copy

		# Try to connect again.
		db = momoko.AsyncClient(
			{
				'host': self.credentials['hostname'],
				'port': self.credentials['port'],
				'user': self.credentials['username'],
				'password': self.credentials['password'],
				'ioloop': self.configuration.io_loop
			}
		)

		try:
			db.execute("SELECT id FROM foo", callback=self.stop)
			result = self.wait()

			for row in result:
				self.assertEquals(row[0], 1, "Result was not as expected.")

			self.assertFalse(True, "Did not raise exception as expected.")
		except psycopg2.OperationalError, ex:

			self.assertTrue(True, "Raised exception correctly.")

		db.close()
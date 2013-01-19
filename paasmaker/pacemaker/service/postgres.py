
from base import BaseService, BaseServiceTest
import paasmaker

import momoko
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

	def create(self, name, callback, error_callback):
		# Choose a username, password, and database name.
		# The username and database name are based off the supplied name.
		username = self._safe_name(name)
		database = username
		password = self._generate_password()

		self.logger.info("Chosen username/database name %s", username)

		def on_database_created(result):
			# Done!
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

		self.db = momoko.AsyncClient(
			{
				'host': self.options['hostname'],
				'port': self.options['port'],
				'user': self.options['username'],
				'password': self.options['password'],
				'ioloop': self.configuration.io_loop
			}
		)

		on_connected()

	def update(self, name, existing_credentials, callback, error_callback):
		# No action to take here.
		callback(existing_credentials, "Successfully modified service.")

	def remove(self, name, existing_credentials, callback, error_callback):
		error_callback("Removing not implemented.")

class PostgresServiceTest(BaseServiceTest):
	def setUp(self):
		super(PostgresServiceTest, self).setUp()

		self.server = paasmaker.util.managedpostgres.ManagedPostgres(self.configuration)
		self.server.configure(
			self.configuration.get_scratch_path_exists('postgres'),
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
		#print str(result)

		# We should have got here at this stage.
		# The above would have raised an exception if it didn't work.
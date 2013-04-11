#
# Paasmaker - Platform as a Service
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#

import platform
import copy
import os
import tempfile

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
	binary_path = colander.SchemaNode(colander.String(),
		title="Postgres Binaries Path",
		description="The path to the postgres binaries, specifically pg_dump and psql. If auto, it will use the one in the path.",
		default="auto",
		missing="auto")

class PostgresServiceParametersSchema(colander.MappingSchema):
	# No parameters required. Plugins just ask for a database.
	pass

class PostgresServiceExportParametersSchema(colander.MappingSchema):
	# No options available.
	pass

class PostgresServiceImportParametersSchema(colander.MappingSchema):
	# No options available.
	pass

class PostgresService(BaseService):
	MODES = {
		paasmaker.util.plugin.MODE.SERVICE_CREATE: PostgresServiceParametersSchema(),
		paasmaker.util.plugin.MODE.SERVICE_DELETE: None,
		paasmaker.util.plugin.MODE.SERVICE_EXPORT: PostgresServiceExportParametersSchema(),
		paasmaker.util.plugin.MODE.SERVICE_IMPORT: PostgresServiceImportParametersSchema()
	}
	OPTIONS_SCHEMA = PostgresServiceConfigurationSchema()
	API_VERSION = "0.9.0"

	def _postgres_path(self):
		if self.options['binary_path'] == 'auto':
			if platform.system() == 'Darwin':
				# Postgres binaries are in the path on OSX.
				return ""
			else:
				# TODO: This is Ubuntu specific.
				return "/usr/lib/postgresql/9.1/bin"
		else:
			return self.options['binary_path']

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

	def export(self, name, credentials, complete_callback, error_callback, stream_callback):
		# Export the contents of the database.
		# From the credentials, basically run pg_dump on the database.
		pwfile = tempfile.mkstemp()[1]
		pwfile_fp = open(pwfile, 'w')
		pwfile_fp.write("%s:%d:%s:%s:%s\n" % (
				credentials['hostname'],
				credentials['port'],
				credentials['database'],
				credentials['username'],
				credentials['password']
			)
		)
		pwfile_fp.close()

		commandline = [
			os.path.join(self._postgres_path(), 'pg_dump'),
			'-h', credentials['hostname'],
			'-p', str(credentials['port']),
			'-U', credentials['username'],
			'-w', # Never ask for a password.
			credentials['database']
		]

		environment = copy.deepcopy(os.environ)
		environment['PGPASSFILE'] = pwfile

		def buffer_errors(data):
			buffer_errors.error_output += data

		buffer_errors.error_output = ""

		def completed(code):
			os.unlink(pwfile)
			if code == 0:
				complete_callback("Completed export successfully.")
			else:
				error_callback("Failed with error code %d.\nOutput: %s" % (code, buffer_errors.error_output))

		reader = paasmaker.util.popen.Popen(
			commandline,
			on_exit=completed,
			on_stdout=stream_callback,
			on_stderr=buffer_errors,
			io_loop=self.configuration.io_loop,
			env=environment
		)

	def export_filename(self, service):
		filename = super(PostgresService, self).export_filename(service)
		return filename + ".sql"

	def import_file(self, name, credentials, filename, callback, error_callback):
		# Write out the password file.
		pwfile = tempfile.mkstemp()[1]
		pwfile_fp = open(pwfile, 'w')
		pwfile_fp.write("%s:%d:%s:%s:%s\n" % (
				credentials['hostname'],
				credentials['port'],
				credentials['database'],
				credentials['username'],
				credentials['password']
			)
		)
		pwfile_fp.close()

		environment = copy.deepcopy(os.environ)
		environment['PGPASSFILE'] = pwfile

		commandline = [
			os.path.join(self._postgres_path(), 'psql'),
			'-h', credentials['hostname'],
			'-p', str(credentials['port']),
			'-U', credentials['username'],
			'-w', # Never ask for a password.
			credentials['database']
		]

		def completed(message):
			os.unlink(pwfile)
			callback("Successfully imported database.")

		def errored(message, exception=None):
			os.unlink(pwfile)
			error_callback(message, exception=exception)

		self._wrap_import(filename, commandline, completed, errored, environment=environment)

class PostgresServiceTest(BaseServiceTest):
	def _postgres_path(self):
		if platform.system() == 'Darwin':
			# Postgres binaries are in the path on OSX.
			return ""
		else:
			# TODO: This is Ubuntu specific.
			return "/usr/lib/postgresql/9.1/bin"

	def setUp(self):
		super(PostgresServiceTest, self).setUp()

		self.server = paasmaker.util.postgresdaemon.PostgresDaemon(self.configuration)
		self.server.configure(
			self.configuration.get_scratch_path_exists('postgres'),
			self._postgres_path(),
			self.configuration.get_free_port(),
			'127.0.0.1',
			self.stop,
			self.stop,
			password="test"
		)
		self.wait()
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
				'password': 'test',
				'binary_path': self._postgres_path()
			},
			'Postgres Service'
		)

	def tearDown(self):
		if hasattr(self, 'server'):
			self.server.destroy(self.stop, self.stop)
			self.wait(timeout=10)

		super(PostgresServiceTest, self).tearDown()

	def test_simple(self):
		logger = self.configuration.get_job_logger('testservice')
		service = self.registry.instantiate(
			'paasmaker.service.postgres',
			paasmaker.util.plugin.MODE.SERVICE_CREATE,
			{},
			logger=logger
		)

		service.create('test', self.success_callback, self.failure_callback)

		try:
			self.wait()
		except psycopg2.OperationalError, ex:
			# Ignore this exception - it's an async handler
			# trying to reconnect to the now-stopped Postgres server.
			pass

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

		# Export the database.
		service.export(
			'testlongname',
			credentials_copy,
			self.success_remove_callback,
			self.failure_callback,
			self.sink_export
		)
		self.wait()

		self.assertTrue(self.success, "Did not succeed to export.")
		self.assertIn('CREATE TABLE foo', self.export_data, "Export data missing table data.")

		# Now attempt to delete the service.
		service.remove('test', credentials_copy, self.success_remove_callback, self.failure_callback)
		self.wait()

		self.assertTrue(self.success, "Did not succeed.")

		self.credentials = credentials_copy

		# Try to export the DB again.
		service.export(
			'testlongname',
			credentials_copy,
			self.success_remove_callback,
			self.failure_callback,
			self.sink_export
		)
		self.wait()

		self.assertFalse(self.success, "Succeeded when it should not have.")
		self.assertIn("FATAL", self.message, "Wrong error message.")

		self.credentials = credentials_copy

		# Create a new database and import the backup into it.
		service.create('test2', self.success_callback, self.failure_callback)
		self.wait()

		import_credentials = self.credentials

		self.assertTrue(self.success, "Did not create new database.")

		tempimport = tempfile.mkstemp()[1]
		open(tempimport, 'w').write(self.export_data)

		service.import_file(
			'test2',
			import_credentials,
			tempimport,
			self.success_remove_callback,
			self.failure_callback
		)
		self.wait()

		self.assertTrue(self.success, "Did not successfully import.")

		# Connect to the database and execute a query.
		db = momoko.AsyncClient(
			{
				'host': import_credentials['hostname'],
				'port': import_credentials['port'],
				'user': import_credentials['username'],
				'password': import_credentials['password'],
				'ioloop': self.configuration.io_loop
			}
		)

		db.execute("SELECT id FROM foo", callback=self.stop)
		result = self.wait()

		for row in result:
			self.assertEquals(row[0], 1, "Result was not as expected.")

		db.close()
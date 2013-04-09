#
# Paasmaker - Platform as a Service
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#

import tempfile
import os

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

class MySQLServiceExportParametersSchema(colander.MappingSchema):
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

		connection.close()

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

		connection.close()

		self._callback("Completed successfully.")

# MySQL service.
class MySQLService(BaseService):
	MODES = {
		paasmaker.util.plugin.MODE.SERVICE_CREATE: MySQLServiceParametersSchema(),
		paasmaker.util.plugin.MODE.SERVICE_DELETE: None,
		paasmaker.util.plugin.MODE.SERVICE_EXPORT: MySQLServiceExportParametersSchema()
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

	def export(self, name, credentials, complete_callback, error_callback, stream_callback):
		# Export the contents of the database.
		# From the credentials, basically run mysqldump on the database.
		# Write the password out to a temporary file (so it doesn't appear on the command line).
		pwfile = tempfile.mkstemp()[1]
		pwfile_fp = open(pwfile, 'w')
		pwfile_fp.write("[client]\n")
		pwfile_fp.write("password=")
		pwfile_fp.write(credentials['password'])
		pwfile_fp.write("\n")
		pwfile_fp.close()

		commandline = [
			'mysqldump',
			'--defaults-extra-file=' + pwfile,
			'-h', credentials['hostname'],
			'--port', str(credentials['port']),
			'-u', credentials['username'],
			credentials['database']
		]

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
			io_loop=self.configuration.io_loop
		)

	def export_filename(self, service):
		filename = super(MySQLService, self).export_filename(service)
		return filename + ".sql"

class MySQLServiceTest(BaseServiceTest):
	def setUp(self):
		super(MySQLServiceTest, self).setUp()

		self.server = paasmaker.util.mysqldaemon.MySQLDaemon(self.configuration)
		self.server.configure(
			self.configuration.get_scratch_path_exists('mysql'),
			self.configuration.get_free_port(),
			'127.0.0.1',
			self.stop,
			self.stop,
			password="test"
		)
		result = self.wait()
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
			self.server.destroy(self.stop, self.stop)
			self.wait()

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

		connection.close()

		# Export the database.
		service.export(
			'testlongname',
			credentials,
			self.success_remove_callback,
			self.failure_callback,
			self.sink_export
		)
		self.wait()

		self.assertTrue(self.success, "Did not succeed to export.")
		self.assertIn('`foo`', self.export_data, "Export data missing table data.")

		# Now remove the database.
		service.remove('testlongname', credentials, self.success_remove_callback, self.failure_callback)
		self.wait()

		self.assertTrue(self.success, "Service deletion was not successful.")

		# Try to export the DB again.
		service.export(
			'testlongname',
			credentials,
			self.success_remove_callback,
			self.failure_callback,
			self.sink_export
		)
		self.wait()

		self.assertFalse(self.success, "Succeeded when it should not have.")
		self.assertIn("Unknown database", self.message, "Wrong error message.")

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
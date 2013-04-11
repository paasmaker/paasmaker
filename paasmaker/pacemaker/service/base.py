#
# Paasmaker - Platform as a Service
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#

import uuid
import re
import time
import datetime
import os
import pipes
import tempfile

import tornado.testing
import paasmaker

# Base service.
class BaseService(paasmaker.util.plugin.Plugin):

	def create(self, name, callback, error_callback):
		"""
		Create the service, using the parameters supplied by the application.

		Call the callback with a dict of credentials that the application
		will use to connect to the service. You should try to return a dict
		with the keys ``hostname``, ``username``, ``password``, ``database``,
		``protocol``, and ``port`` where appropriate for your service.

		The ``protocol`` key is quite important, as it allows the application
		to figure out what type a service is.

		Where possible, use the user-supplied name to create the service,
		so the service is later identifyable outside of Paasmaker - for example,
		if you query the MySQL server directly for a list of databases.
		The BaseService provides a helper function, called ``_safe_name()``
		that can convert the name parameter into a safe name for common
		systems.

		Your code might look as follows::

			def create(self, name, callback, error_callback):
				database_name = self._safe_name(name, max_length=16)
				# ... create your database here ...
				credentials = {
					'hostname': 'localhost',
					'username': database_name,
					'database': database_name,
					'password': 'super secret password',
					'port': 12345,
					'protocol': 'mysql'
				}

				callback(credentials, "Created successfully.")

		:arg str name: The user-selected name for the service.
		:arg callable callback: The callback to call once created.
		:arg callable error_callback: A callback to call if an error occurs.
		"""
		raise NotImplementedError("You must implement create().")

	def update(self, name, existing_credentials, callback, error_callback):
		"""
		Update the service (if required) returning new credentials. In many
		cases this won't make sense for a service, but is provided for a few
		services for which it does make sense. If you don't need it, just
		call the callback immediately.

		For example::

			def update(self, name, existing_credentials, callback, error_callback):
				callback(existing_credentials, "Updated successfully.")

		:arg str name: The user-selected name for the service.
		:arg dict existing_credentials: The existing service credentials.
		:arg callable callback: The callback to call with updated credentials.
		:arg error_callback: The error callback in case something goes wrong.
		"""
		callback(existing_credentials, "No changes required.")

	def remove(self, name, existing_credentials, callback, error_callback):
		"""
		Remove the service, using the options supplied by the application,
		and the credentials created when the service was created.

		You should delete any associated database. The user would have already
		been informed of this action and what it will do, so you do not need
		to ask for permission here.

		The supplied existing_credentials can be used to figure out what database
		to remove.

		:arg str name: The user-supplied name for the service.
		:arg dict existing_credentials: The existing service credentials.
		:arg callable callback: The callback to call once complete. Supply
			it a single argument; a string with a message.
		:arg callable error_callback: The callback to call if an error
			occurs.
		"""
		raise NotImplementedError("You must implement remove().")

	def export(self, name, credentials, complete_callback, error_callback, stream_callback):
		"""
		Export this service in a format that makes sense for this service.
		For example, for the MySQL service, this would be the output of
		``mysqldump``.

		The ``complete_callback`` argument is called when the export is complete.
		The ``error_callback`` is called if something goes wrong.
		The ``stream_callback`` is called with a chunk of data from the backend,
		for you to do what you want with. For HTTP, you might stream this
		back to the client.

		The plugin metadata requires that options be passed in when you
		instantiate this plugin. This can be used to control options when exporting
		the data.

		:arg str name: The name of the service.
		:arg dict credentials: The credentials for the service.
		:arg callable complete_callback: The callback to call when done.
		:arg callable error_callback: The callback to call on error.
		:arg callable stream_callback: The callback to call with a chunk of data.
			Don't assume that this chunk of data can stand on it's own.
		"""
		raise NotImplementedError("export() is not implemented for this service.")

	def export_cancel(self):
		"""
		Cancel an export in progress.
		"""
		pass

	def export_filename(self, service):
		"""
		Return a filename for the export. You can use this default and then add
		an appropriate extension on the end for your use case.

		This is called before export().

		:arg Service service: An open service ORM object. You can use this
			to pull attributes for your filename.
		"""
		filename = "export_%s_%d_%s" % (
			service.name,
			service.id,
			datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
		)

		return filename

	def import_file(self, name, credentials, filename, callback, error_callback):
		"""
		Import the given file into the service. Exactly how this is performed
		depends on your service.

		:arg str name: The name of the service.
		:arg dict credentials: The credentials of the service.
		:arg str filename: The filename that contains the data to import.
		:arg callable callback: The callback to call once done.
		:arg callable error_callback: The callback to call on error.
		"""
		raise NotImplementedError("import_file() is not implemented for this service.")

	def import_cancel(self):
		"""
		Cancel the import process. The default implementation kills off the
		internal import process launched via _wrap_import(). If you don't use
		this, you'll want to implement your own version.
		"""
		if hasattr(self, 'import_process'):
			self.import_process.kill()

	def _safe_name(self, name, max_length=50):
		"""
		Internal helper function to clean a user-supplied service name.
		Please make sure this produces clean names for your particular
		service before using it.

		It takes these actions:

		* Converts the service name to lower case.
		* Strips any characters other than [A-Za-z0-9].
		* Appends 8 characters of a new UUID to the name.
		* Limits the length to the given max length. It will
		  remove parts of the name to ensure that all of the
		  unique characters appear in the output.

		:arg str name: The service name.
		:arg int max_length: The maximum length of the output. The name
			is not longer than this length.
		"""
		unique = str(uuid.uuid4())[0:8]
		clean_name = re.sub(r'[^A-Za-z0-9]', '', name)
		clean_name = clean_name.lower()

		if len(clean_name) + len(unique) > max_length:
			# It'll be too long if we add the name + unique together.
			# Clip the name.
			clean_name = clean_name[0:max_length - len(unique)]

		output_name = "%s%s" % (clean_name, unique)

		return output_name

	def _generate_password(self, max_length=50):
		"""
		Internal helper function to generate a random password for you.
		It internally generates a 36 character UUID and returns that,
		which should be unique and random enough for most purposes. It
		uses Python's uuid4() which is based on random numbers.

		:arg int max_length: The maximum length of the password. The
			UUID is trimmed if needed to make it fit in this length.
		"""
		password = str(uuid.uuid4())

		if len(password) > max_length:
			password = password[0:max_length]

		return password

	def _guess_compression(self, filename, callback, error_callback):
		"""
		Internal helper function to see if the given file is compressed,
		and return a type based on that.

		This is designed to be used in ``import_file()``. Uploaded files
		don't have their original filename, making it hard to guess what
		their contents might have been, so this function reads the file to
		check.

		The callback is called with one of a few values:
		* gzip
		* bzip2
		* unknown (assumedly not compressed)

		:arg str filename: The filename to check.
		:arg callable callback: The callback to call with the result.
		:arg callable error_callback: The callback used if an error occurs.
		"""

		def file_result(code):
			if code == 0:
				# Success! Read the output.
				if "gzip compressed data" in file_result.buffer:
					callback("gzip")
				elif "bzip2 compressed data" in file_result.buffer:
					callback("bzip2")
				else:
					callback("unknown")
			else:
				error_callback("Error whilst determining the type of file %s. Check to see if the 'file' binary is in the path." % filename)

		file_result.buffer = ""

		def buffer_output(data):
			# Store stdout for a while.
			file_result.buffer += data

		checker = paasmaker.util.popen.Popen(
			['file', filename],
			on_stdout=buffer_output,
			on_exit=file_result,
			io_loop=self.configuration.io_loop
		)

	def _wrap_import(self, filename, command, callback, error_callback, environment=None):
		"""
		Helper function to wrap the supplied command around a cat. Eg,
		it will basically run this in a shell:

		.. code-block:: bash

			$ cat filename | command argument ...

		It will try to guess the compression and replace ``cat`` with ``zcat``
		or ``bzcat`` as appropriate.

		The instance variable ``import_process`` is set, which can be used to cancel
		the import.

		:arg str filename: The filename to import from.
		:arg list command: The command to execute to import.
		:arg callable callback: The callback to call once done.
		:arg callable error_callback: The error callback to call on error.
		"""
		# Write out a small shell script to do the import.
		scriptfile = tempfile.mkstemp()[1]
		scriptfile_fp = open(scriptfile, 'w')
		#scriptfile_fp.write("\nset -xe\n")
		scriptfile_fp.write("set -o pipefail\n")

		self.logger.debug("Guessing compression...")

		def detected_compression(compression):
			dcommand = 'cat'
			if compression == 'gzip':
				dcommand = 'zcat'
			if compression == 'bzip2':
				dcommand = 'bzcat'

			self.logger.info("Detected compression %s, using %s to decompress.", compression, dcommand)

			scriptfile_fp.write(dcommand)
			scriptfile_fp.write(' ')
			scriptfile_fp.write(filename)
			scriptfile_fp.write(' | ')

			for element in command:
				scriptfile_fp.write(pipes.quote(element))
				scriptfile_fp.write(' ')

			scriptfile_fp.write('\n')
			scriptfile_fp.close()

			self.logger.info("Starting import.")
			self.log_fp = self.logger.takeover_file()

			def exited(code):
				self.logger.untakeover_file(self.log_fp)
				self.logger.info("Exited with code %d.", code)
				os.unlink(scriptfile)
				if code == 0:
					callback("Successfully imported.")
				else:
					error_callback("Failed to import - exit code %d." % code)

			self.import_process = paasmaker.util.Popen(
				['bash', scriptfile],
				on_exit=exited,
				stdout=self.log_fp,
				stderr=self.log_fp,
				io_loop=self.configuration.io_loop,
				env=environment
			)

		self._guess_compression(filename, detected_compression, error_callback)

class BaseServiceTest(tornado.testing.AsyncTestCase):
	def setUp(self):
		super(BaseServiceTest, self).setUp()
		self.configuration = paasmaker.common.configuration.ConfigurationStub(0, ['pacemaker'], io_loop=self.io_loop)
		self.registry = self.configuration.plugins
		self.credentials = None
		self.success = None
		self.message = None
		self.exception = None
		self.export_data = ""

	def tearDown(self):
		self.configuration.cleanup(self.stop, self.stop)
		self.wait()
		super(BaseServiceTest, self).tearDown()

	def success_callback(self, credentials, message):
		self.success = True
		self.exception = None
		self.message = message
		self.credentials = credentials
		self.stop()

	def success_remove_callback(self, message):
		self.success = True
		self.exception = None
		self.message = message
		self.credentials = None
		self.stop()

	def failure_callback(self, message, exception=None):
		self.success = False
		self.message = message
		self.exception = exception
		self.credentials = None
		self.stop()

	def short_wait_hack(self, length=0.1):
		self.io_loop.add_timeout(time.time() + length, self.stop)
		self.wait()

	def sink_export(self, data):
		self.export_data += data
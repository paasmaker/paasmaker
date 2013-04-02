#
# Paasmaker - Platform as a Service
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#

import os
import signal
import shutil
import json
import logging
import time
import tempfile

from processcheck import ProcessCheck

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

class ManagedDaemonError(Exception):
	"""
	Base error for exceptions raised by managed Daemons.
	"""
	pass

class ManagedDaemon(object):
	"""
	Managed daemon base class, provding helpers to other managed daemons.
	"""

	def __init__(self, configuration):
		self.configuration = configuration
		self.parameters = {}
		self.client = None

	# Your subclass should supply a configure() method and a start()
	# method. And then override anything else it might need.

	def load_parameters(self, working_dir):
		"""
		Load the parameters from the working directory.

		Throws an exception if that directory is not configured.

		:arg str working_dir: The working directory for this daemon.
		"""
		parameters_path = self.get_parameters_path(working_dir)
		config_path = self.get_configuration_path(working_dir)
		if os.path.exists(parameters_path):
			# TODO: Some more error checking.
			fp = open(parameters_path, 'r')
			contents = fp.read()
			self.parameters = json.loads(contents)
			fp.close()
		else:
			raise ManagedDaemonError('No configuration file found in the working directory. Looking for %s.' % config_path)

	def save_parameters(self):
		"""
		Save the parameters file to disk.
		"""
		# TODO: More error checking.
		fp = open(self.get_parameters_path(self.parameters['working_dir']), 'w')
		fp.write(json.dumps(self.parameters))
		fp.close()

	def get_parameters_path(self, working_dir):
		"""
		Get the parameters configuration path. Override if you need to.
		"""
		return os.path.join(working_dir, 'service.json')

	def get_configuration_path(self, working_dir):
		"""
		Get the server configuration path. Override if you need to.
		"""
		return os.path.join(working_dir, 'service.conf')

	def is_running(self, keyword=None):
		"""
		Check to see if this managed daemon is running or not.
		"""
		pid = self.get_pid()
		if pid:
			# Do an advanced check on pid.
			return ProcessCheck.is_running(pid, keyword)
		else:
			# No PID at all. Not running.
			return False

	def get_port(self):
		"""
		Get the TCP port that this managed daemon should be
		listening on.
		"""
		return self.parameters['port']

	def get_pid(self):
		"""
		Gets the PID of the running instance. This just reads the on disk
		PID file, and may not as such indicate that it's running. Returns
		None if no pid file found.
		"""
		pidpath = self.get_pid_path()
		if os.path.exists(pidpath):
			fp = open(pidpath, 'r')
			raw = fp.read()
			fp.close()
			if len(raw) == 0:
				# Blank PID file.
				# TODO: We're assuming it's not running...
				return None
			else:
				pid = int(raw)
				return pid
		else:
			return None

	def get_pid_path(self):
		raise NotImplementedError("You must implement get_pid_path().")

	def start_if_not_running(self, callback, error_callback):
		"""
		Start up the managed daemon if it's not running.

		:arg callable callback: The callback for when it is running.
		:arg callback error_callback: The callback for when an error
			occurs.
		"""
		if not self.is_running():
			logging.debug("Starting up managed daemon as it's not currently running.")
			self.start(callback, error_callback)
		else:
			logging.debug("Managed daemon already running.")
			callback("Already running.")

	def destroy(self, callback):
		"""
		Destroy this managed instance. Typically used for unit tests
		to be able to remove all temporary files.
		"""
		raise NotImplementedError("You must implement destroy()")

	def stop(self, callback, error_callback, sig=signal.SIGTERM):
		"""
		Stop this instance of the daemon, allowing for it to be restarted later.

		Optionally, specify the signal to get the daemon to stop.
		"""
		pid = self.get_pid()
		if pid:
			os.kill(pid, sig)

		# Wait for the process to finish.
		self._wait_until_stopped(callback, error_callback)

	def _wait_until_port_inuse(self, port, callback, error_callback, timeout=5):
		"""
		Helper function to wait until a port is in use.

		:arg int port: The port to wait for.
		:arg callable callback: The callback to call when in use.
		:arg callable error_callback: The error callback to call on timeout.
		:arg int timeout: The number of seconds to wait.
		"""
		self.configuration.port_allocator.wait_until_port_used(
			self.configuration.io_loop,
			port,
			timeout,
			callback,
			error_callback
		)

	def _wait_until_port_free(self, port, callback, error_callback, timeout=5):
		"""
		Helper function to wait until a port is free.

		:arg int port: The port to wait for.
		:arg callable callback: The callback to call when free.
		:arg callable error_callback: The error callback to call on timeout.
		:arg int timeout: The number of seconds to wait.
		"""
		self.configuration.port_allocator.wait_until_port_free(
			self.configuration.io_loop,
			port,
			timeout,
			callback,
			error_callback
		)

	def _wait_until_stopped(self, callback, error_callback, timeout=5):
		"""
		Helper function to wait until a process is stopped.

		:arg str callback: The callback to call.
		:arg str error_callback: The error callback to call.
		:arg int timeout: The number of seconds to wait.
		"""
		max_time = time.time() + timeout

		def check():
			if max_time < time.time():
				# Too long.
				error_callback("Timed out waiting for process to exit.")
			elif self.is_running():
				# Wait a bit longer.
				self.configuration.io_loop.add_timeout(time.time() + 0.2, check)
			else:
				# It's finished.
				callback("Process has finished.")

		check()

	def _fetchable_output(self, data):
		"""
		Helper function to store subprocess output, to fetch back later
		and use in error reports.

		This is to workaround a few issues with Popen() and redirecting
		stdout/stderr directly to files.

		Here is how to use it:

		.. code-block:: python

			def exit_function(code):
				if code == 0:
					callback("Success")
				else:
					error_callback("Error starting: " + self._fetch_output())

			paasmaker.util.popen.Popen(
				command_line,
				on_stdout=self._fetchable_output,
				redirect_stderr=True,
				on_exit=exit_function,
				io_loop=self.configuration.io_loop
			)
		"""
		if hasattr(self, 'fetchable_output_log'):
			self.fetchable_output_log_fp.write(data)
		else:
			self.fetchable_output_log = tempfile.mkstemp()[1]
			self.fetchable_output_log_fp = open(self.fetchable_output_log, 'w')
			self.fetchable_output_log_fp.write(data)

	def _fetch_output(self):
		"""
		Helper function to fetch process output. See _fetchable_output() for
		a description.
		"""
		if hasattr(self, 'fetchable_output_log'):
			self.fetchable_output_log_fp = open(self.fetchable_output_log, 'r')
			contents = self.fetchable_output_log_fp.read()
			self.fetchable_output_log_fp.close()
			os.unlink(self.fetchable_output_log)
			del self.fetchable_output_log
			del self.fetchable_output_log_fp
			return contents
		else:
			return ''

	def __del__(self):
		# Clean up any output log, if present.
		if hasattr(self, 'fetchable_output_log'):
			self.fetchable_output_log_fp.close()
			if os.path.exists(self.fetchable_output_log):
				os.unlink(self.fetchable_output_log)

import os
import signal
import shutil
import json
import logging

from processcheck import ProcessCheck

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

class ManagedDaemonError(Exception):
	pass

class ManagedDaemon(object):

	def __init__(self, configuration):
		self.configuration = configuration
		self.parameters = {}
		self.client = None

	# Your subclass should supply a configure() method.
	# And a few other things as well - a start() specifically.

	def load_parameters(self, working_dir):
		"""
		Load the parameters from the working directory.

		Throws an exception if that directory is not configured.
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
		pid = self.get_pid()
		if pid:
			# Do an advanced check on pid.
			return ProcessCheck.is_running(pid, keyword)
		else:
			# No PID at all. Not running.
			return False

	def get_pid(self):
		"""
		Gets the PID of the running instance. This just reads the on disk
		PID file, and may not as such indicate that it's running. Returns
		None if no pid file found.
		"""
		pidpath = self.get_pid_path()
		if os.path.exists(pidpath):
			fp = open(pidpath, 'r')
			pid = int(fp.read())
			fp.close()
			return pid
		else:
			return None

	def get_pid_path(self):
		raise NotImplementedError("You must implement get_pid_path().")

	def start_if_not_running(self, callback, error_callback):
		if not self.is_running():
			logging.debug("Starting up managed daemon as it's not currently running.")
			self.start(callback, error_callback)
		else:
			logging.debug("Managed daemon already running.")
			callback("Already running.")

	def destroy(self):
		raise NotImplementedError("You must implement destroy()")

	def stop(self, sig=signal.SIGTERM):
		"""
		Stop this instance of the daemon, allowing for it to be restarted later.
		"""
		pid = self.get_pid()
		if pid:
			os.kill(pid, sig)

import logging
import os
import signal
import json
import subprocess
import unittest
import uuid
import time
import paasmaker
import datetime

class CommandSupervisor():
	def __init__(self, configuration, logfile):
		self.configuration = configuration
		self.process = None
		self.logfile = logfile

	def run(self, data):
		# Prepare to run.
		# NOTE: Assumes that data is as expected...
		job_id = data['job_id']
		job_file = self.configuration.get_job_log_path(job_id)
		command = data['command'] # Should be an array!
		shell = False
		if data.has_key('shell'):
			shell = data['shell']

		# Install a signal handler to abort this process.
		# NOTE: This assumes that you're running this code in
		# a seperate supervisor script. If you don't, weird stuff
		# will happen. However, this is blocking so you kind of
		# have to run this in a seperate process anyway.
		signal.signal(signal.SIGHUP, self.signal_handler)

		try:
			self.special_logger(self.logfile, "Running command: %s" % " ".join(command))
			job_fp = open(job_file, 'ab')
			self.process = subprocess.Popen(
				command,
				stdin=None,
				stdout=job_fp,
				stderr=job_fp,
				shell=shell
			)

			# Wait for it to complete, or for us to be killed.
			self.process.wait()
			job_fp.close()

			# And record the result.
			self.special_logger(self.logfile, "Completed with result code %d" % self.process.returncode)

			# TODO: Announce the completion by pubsub.

		except OSError, ex:
			self.special_logger(self.logfile, "Failed to execute subcommand: %s" % str(ex))

	def kill(self):
		if self.process:
			self.special_logger(self.logfile, "Killing off this process.")
			os.kill(self.pid, signal.SIGTERM)

	def signal_handler(self, signum, frame):
		# Attempt to kill our child process.
		# (Think of the children!)
		self.kill()

	@staticmethod
	def special_logger(filename, message):
		f = open(filename, 'a')
		f.write(datetime.datetime.utcnow().isoformat())
		f.write(" ")
		f.write(message)
		f.write("\n")
		f.close()

class CommandSupervisorLauncher():
	def __init__(self, configuration):
		self.configuration = configuration
		self.process = None

	def launch(self, job_id, command):
		# TODO: Allow environment variables.
		payload = {}
		payload['job_id'] = job_id
		payload['command'] = command

		payload_path = self.configuration.get_scratch_path("launch_%s.json" % job_id)
		open(payload_path, 'w').write(json.dumps(payload))

		# Launch it.
		supervisor = self.configuration.get_supervisor_path()
		log_file = self.configuration.get_job_log_path(job_id)
		# The second argument is optional, but allows unit tests to work properly.
		self.process = subprocess.Popen([supervisor, log_file, payload_path, self.configuration.filename])

class CommandSupervisorTest(unittest.TestCase):
	def setUp(self):
		self.configuration = paasmaker.configuration.ConfigurationStub([])
		super(CommandSupervisorTest, self).setUp()
	def tearDown(self):
		self.configuration.cleanup()
		super(CommandSupervisorTest, self).tearDown()

	def test_normal_execution(self):
		# Make me a launcher.
		job_id = str(uuid.uuid4())
		launcher = CommandSupervisorLauncher(self.configuration)
		launcher.launch(job_id, ["echo", "test"])

		# Wait for the subprocess to finish.
		launcher.process.wait()

		# Check that it output what we expected.
		job_path = self.configuration.get_job_log_path(job_id)
		job_contents =""
		if os.path.exists(job_path):
			job_contents = open(job_path, 'r').read()

		self.assertIn("test", job_contents, "Missing output.")
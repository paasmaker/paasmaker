
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
		pidfile = self.configuration.get_scratch_path("%s.pid" % job_id)

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

			# Write out OUR pid.
			pid_fd = open(pidfile, 'w')
			pid_fd.write(str(os.getpid()))
			pid_fd.close()

			# Wait for it to complete, or for a signal.
			self.process.wait()

			# Close off the output file.
			job_fp.close()

			# Remove the pidfile.
			os.unlink(pidfile)

			# And record the result.
			self.special_logger(self.logfile, "Completed with result code %d" % self.process.returncode)

			# TODO: Announce the completion by pubsub.

		except OSError, ex:
			self.special_logger(self.logfile, "Failed to execute subcommand: %s" % str(ex))

	def kill(self):
		if self.process:
			self.special_logger(self.logfile, "Killing off this process.")
			os.kill(self.process.pid, signal.SIGTERM)

	def signal_handler(self, signum, frame):
		# Attempt to kill our child process.
		# (Think of the children!)
		self.special_logger(self.logfile, "Got signal %d" % signum)
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

		payload_path = self.configuration.get_scratch_path("%s_launch.json" % job_id)
		open(payload_path, 'w').write(json.dumps(payload))

		# Launch it.
		supervisor = self.configuration.get_supervisor_path()
		log_file = self.configuration.get_job_log_path(job_id)
		# The second argument is optional, but allows unit tests to work properly.
		self.process = subprocess.Popen([supervisor, log_file, payload_path, self.configuration.filename])

	def kill(self):
		os.kill(self.process.pid, signal.SIGHUP)

	def kill_job(self, job_id):
		pidfile = self.configuration.get_scratch_path("%s.pid" % job_id)
		if os.path.exists(pidfile):
			pid = int(open(pidfile, 'r').read())
			os.kill(pid, signal.SIGHUP)

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

	def test_abort_execution(self):
		# Make me a launcher.
		job_id = str(uuid.uuid4())
		launcher = CommandSupervisorLauncher(self.configuration)
		launcher.launch(job_id, ["./misc/hanger-test.sh"])

		# Give the process some time to start.
		time.sleep(0.5)

		# Now kill it off.
		launcher.kill()

		# Wait for everything to settle down.
		time.sleep(0.5)

		# Check that it output what we expected.
		job_path = self.configuration.get_job_log_path(job_id)
		job_contents =""
		if os.path.exists(job_path):
			job_contents = open(job_path, 'r').read()

		self.assertIn("Start...", job_contents, "Missing output.")
		self.assertIn("Killing", job_contents, "Missing output.")
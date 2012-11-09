
import logging
import os
import signal
import json
import subprocess
import unittest
import uuid
import time
import datetime
import urllib2

import paasmaker
from paasmaker.common.controller import BaseController, BaseControllerTest

import tornado

class CommandSupervisor(object):
	def __init__(self, configuration, logfile):
		self.configuration = configuration
		self.process = None
		self.logger = None
		self.job_fp = None

	def run(self, data):
		# Prepare to run.
		# NOTE: Assumes that data is as expected...
		instance_id = data['instance_id']
		self.logger = self.configuration.get_job_logger(instance_id)
		command = data['command'] # Should be an array!
		shell = False
		if data.has_key('shell'):
			shell = data['shell']
		# TODO: Make this a subdir of the scratch dir.
		pidfile = self.configuration.get_scratch_path("%s.pid" % instance_id)

		# Install a signal handler to abort this process.
		# NOTE: This assumes that you're running this code in
		# a seperate supervisor script. If you don't, weird stuff
		# will happen. However, this is blocking so you kind of
		# have to run this in a seperate process anyway.
		signal.signal(signal.SIGHUP, self.signal_handler)

		try:
			self.logger.info("Running command: %s", " ".join(command))
			self.job_fp = self.logger.takeover_file()
			self.process = subprocess.Popen(
				command,
				stdin=None,
				stdout=self.job_fp,
				stderr=self.job_fp,
				shell=shell,
				cwd=data['cwd'],
				env=data['environment']
			)

			# Write out OUR pid.
			pid_fd = open(pidfile, 'w')
			pid_fd.write(str(os.getpid()))
			pid_fd.close()

			# Wait for it to complete, or for a signal.
			self.process.wait()

			self.close_off_log()

			# Remove the pidfile.
			os.unlink(pidfile)

			# And record the result.
			self.logger.info("Completed with result code %d", self.process.returncode)

			# Announce the completion.
			self.announce_completion(
				data['port'],
				instance_id,
				data['exit_key'],
				self.process.returncode
			)

		except OSError, ex:
			if self.job_fp:
				self.job_fp.close()
			self.logger.error(ex)
			self.logger.error("Failed to execute subcommand: %s", str(ex))

	def close_off_log(self):
		if self.job_fp:
			self.logger.untakeover_file(self.job_fp)

	def kill(self):
		if self.process:
			os.kill(self.process.pid, signal.SIGTERM)
			self.process.wait()
			self.close_off_log()
			self.logger.info("Killed off child process as requested.")

	def signal_handler(self, signum, frame):
		# Attempt to kill our child process.
		# (Think of the children!)
		self.kill()
		self.logger.info("Got signal %d", signum)

	def announce_completion(self, port, instance_id, exit_key, code, depth=1):
		url = "http://localhost:%d/instance/exit/%s/%s/%d" % \
			(port, instance_id, exit_key, code)
		try:
			response = urllib2.urlopen(url)
		except urllib2.URLError, ex:
			# Retry a few more times.
			if depth < 10:
				time.sleep(5)
				self.announce_completion(port, instance_id, exit_key, code, depth + 1)
			else:
				# TODO: Print ex to log file.
				raise ex

class CommandSupervisorLauncher(object):
	def __init__(self, configuration, instance_id):
		self.configuration = configuration
		self.process = None
		self.instance_id = instance_id

	def launch(self, command, cwd, environment, exit_key, port):
		payload = {}
		payload['instance_id'] = self.instance_id
		payload['command'] = command
		payload['cwd'] = cwd
		payload['environment'] = environment
		payload['exit_key'] = exit_key
		payload['port'] = port

		payload_path = self.get_payload_path()
		fp = open(payload_path, 'w')
		fp.write(json.dumps(payload))
		fp.close()

		# Launch it.
		supervisor = self.configuration.get_supervisor_path()
		log_file = self.configuration.get_job_log_path(self.instance_id)
		# The last argument - config file - is optional,
		# but allows unit tests to work properly.
		self.process = subprocess.Popen([supervisor, log_file, payload_path, self.configuration.filename])

	def get_pid_path(self):
		return self.configuration.get_scratch_path("%s.pid" % self.instance_id)

	def get_payload_path(self):
		return self.configuration.get_scratch_path("%s_supervisor.json" % self.instance_id)

	def kill(self):
		if self.process:
			os.kill(self.process.pid, signal.SIGHUP)
		else:
			pidfile = self.get_pid_path()
			if os.path.exists(pidfile):
				fp = open(pidfile, 'r')
				pid = int(fp.read())
				fp.close()
				os.kill(pid, signal.SIGHUP)

	def is_running(self, instance_id):
		# TODO: This is only a best effort guess.
		pidfile = self.get_pid_path()
		return os.path.exists(pidfile)

class CommandSupervisorTest(BaseControllerTest):
	config_modules = ['heart']

	def get_app(self):
		self.late_init_configuration(self.io_loop)
		routes = paasmaker.heart.controller.instance.InstanceExitController.get_routes({'configuration': self.configuration})
		application = tornado.web.Application(routes, **self.configuration.get_tornado_configuration())
		return application

	def get_misc_path(self):
		return os.path.normpath(os.path.dirname(__file__) + '/../../misc')

	def get_env(self):
		return paasmaker.common.application.environment.ApplicationEnvironment.merge_local_environment(self.configuration, {})

	def get_exit_key(self, instance_id):
		# Add a test instance. Bare minimum info.
		test_instance = {'instance': {'state':'ALLOCATED'}}
		self.configuration.instances.add_instance(instance_id, test_instance)
		return self.configuration.instances.generate_exit_key(instance_id)

	def test_normal_execution(self):
		# Make me a launcher.
		instance_id = str(uuid.uuid4())
		exit_key = self.get_exit_key(instance_id)
		environment = self.get_env()
		launcher = CommandSupervisorLauncher(self.configuration, instance_id)
		launcher.launch(
			["echo", "test"],
			self.get_misc_path(),
			environment,
			exit_key,
			self.get_http_port()
		)

		# Wait for the subprocess to finish.
		finished = None
		while finished is None:
			self.short_wait_hack()
			launcher.process.poll()
			finished = launcher.process.returncode

		# Check that it output what we expected.
		job_path = self.configuration.get_job_log_path(instance_id)
		job_contents =""
		if os.path.exists(job_path):
			job_contents = open(job_path, 'r').read()

		self.assertIn("test", job_contents, "Missing output.")

	def test_abort_execution(self):
		# Make me a launcher.
		instance_id = str(uuid.uuid4())
		exit_key = self.get_exit_key(instance_id)
		environment = self.get_env()
		launcher = CommandSupervisorLauncher(self.configuration, instance_id)
		launcher.launch(
			["./hanger-test.sh"],
			self.get_misc_path(),
			environment,
			exit_key,
			self.get_http_port()
		)

		# Give the process some time to start.
		self.short_wait_hack(length=0.5)

		# Now kill it off.
		launcher.kill()

		# Wait for everything to settle down.
		self.short_wait_hack(length=0.5)

		# Check that it output what we expected.
		job_path = self.configuration.get_job_log_path(instance_id)
		job_contents =""
		if os.path.exists(job_path):
			job_contents = open(job_path, 'r').read()

		self.assertIn("Start...", job_contents, "Missing output.")
		self.assertIn("Killed", job_contents, "Missing output.")

	def test_abort_detached(self):
		# Make me a launcher.
		instance_id = str(uuid.uuid4())
		exit_key = self.get_exit_key(instance_id)
		environment = self.get_env()
		launcher = CommandSupervisorLauncher(self.configuration, instance_id)
		launcher.launch(
			["./hanger-test.sh"],
			self.get_misc_path(),
			environment,
			exit_key,
			self.get_http_port()
		)

		# Give the process some time to start.
		self.short_wait_hack(length=0.5)

		# Create a detached launcher.
		launcher = CommandSupervisorLauncher(self.configuration, instance_id)

		# Kill it off.
		launcher.kill()

		# Wait for everything to settle down.
		self.short_wait_hack(length=0.5)

		# Check that it output what we expected.
		job_path = self.configuration.get_job_log_path(instance_id)
		job_contents =""
		if os.path.exists(job_path):
			job_contents = open(job_path, 'r').read()

		self.assertIn("Start...", job_contents, "Missing output.")
		self.assertIn("Killed", job_contents, "Missing output.")
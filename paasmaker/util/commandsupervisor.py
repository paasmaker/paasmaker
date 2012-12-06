
import subprocess
import uuid
import os
import json
import signal
import shlex

import paasmaker
from paasmaker.common.controller import BaseController, BaseControllerTest
from processcheck import ProcessCheck

import tornado

class CommandSupervisorLauncher(object):
	def __init__(self, configuration, instance_id):
		self.configuration = configuration
		self.instance_id = instance_id

	def launch(self, command, cwd, environment, exit_key, port):
		if isinstance(command, basestring):
			command = shlex.split(str(command))
		payload = {}
		payload['instance_id'] = self.instance_id
		payload['command'] = command
		payload['cwd'] = cwd
		payload['environment'] = environment
		payload['exit_key'] = exit_key
		payload['port'] = port
		payload['log_file'] = self.configuration.get_job_log_path(self.instance_id)
		payload['pidfile'] = self.get_pid_path()

		payload_path = self.get_payload_path()
		fp = open(payload_path, 'w')
		fp.write(json.dumps(payload))
		fp.close()

		# Launch it.
		supervisor = self.configuration.get_supervisor_path()
		# TODO: Make sure this command line is secure and stuff.
		# Why are we doing it this way? We want the process to fork into the background,
		# so if the parent process dies, it doesn't take down any running supervisors.
		command_line = "%s %s > %s 2>&1 &" % (supervisor, payload_path, payload['log_file'])
		subprocess.check_call(command_line, shell=True)

	def get_supervisor_dir(self):
		path = self.configuration.get_scratch_path("supervisor")
		if not os.path.exists(path):
			os.makedirs(path)
		return path

	def get_pid_path(self):
		root = self.get_supervisor_dir()
		return os.path.join(root, "%s.pid" % self.instance_id)

	def get_payload_path(self):
		root = self.get_supervisor_dir()
		return os.path.join(root, "%s.json" % self.instance_id)

	def kill(self):
		pidfile = self.get_pid_path()
		if os.path.exists(pidfile):
			fp = open(pidfile, 'r')
			pid = int(fp.read())
			fp.close()
			os.kill(pid, signal.SIGHUP)

	def is_running(self):
		pidfile = self.get_pid_path()
		if os.path.exists(pidfile):
			fp = open(pidfile, 'r')
			pid = int(fp.read())
			fp.close()
			return ProcessCheck.is_running(pid, 'pm-supervisor')
		else:
			return False

	def get_unreported_exit_code(self):
		root = self.get_supervisor_dir()
		path = os.path.join(root, "%s.exited" % self.instance_id)
		if os.path.exists(path):
			fp = open(path, 'r')
			code = int(fp.read())
			fp.close()
			return code
		else:
			return None

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
		self.short_wait_hack(length=0.5)

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

		self.assertTrue(launcher.is_running(), "Supervisor is not running.")

		# Now kill it off.
		launcher.kill()

		# Wait for everything to settle down.
		self.short_wait_hack(length=0.5)

		self.assertFalse(launcher.is_running(), "Supervisor is still running.")

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

	def test_bad_command(self):
		# Make me a launcher.
		instance_id = str(uuid.uuid4())
		exit_key = self.get_exit_key(instance_id)
		environment = self.get_env()
		launcher = CommandSupervisorLauncher(self.configuration, instance_id)
		launcher.launch(
			["no-such-command"],
			self.get_misc_path(),
			environment,
			exit_key,
			self.get_http_port()
		)

		# Wait for the subprocess to finish.
		self.short_wait_hack(length=0.5)

		# Check that it output what we expected.
		# TODO: Check that it got the correct pubsub broadcast instead.
		job_path = self.configuration.get_job_log_path(instance_id)
		job_contents =""
		if os.path.exists(job_path):
			job_contents = open(job_path, 'r').read()

		self.assertIn("No such file", job_contents, "Missing output.")
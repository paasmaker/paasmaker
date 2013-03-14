
import tempfile
import os
import colander

from base import BasePrepare, BasePrepareTest

import paasmaker

class ShellPrepareConfigurationSchema(colander.MappingSchema):
	# No options defined.
	pass

class ShellPrepareParametersSchema(colander.MappingSchema):
	# Must have a key called commands, which is a list of strings.
	commands = colander.SchemaNode(
		colander.Sequence(),
		colander.SchemaNode(colander.String()),
		title="Commands",
		description="A list of command to run. They can be any bash syntax you would like. Each item in the list becomes a single line in a shell script that is written out and executed."
	)

class ShellPrepare(BasePrepare):
	# NOTE: This plugin can also be used to run commands prior to an instance starting.
	MODES = {
		paasmaker.util.plugin.MODE.PREPARE_COMMAND: ShellPrepareParametersSchema(),
		paasmaker.util.plugin.MODE.RUNTIME_STARTUP: ShellPrepareParametersSchema()
	}
	OPTIONS_SCHEMA = ShellPrepareConfigurationSchema()
	API_VERSION = "0.9.0"

	def prepare(self, environment, directory, callback, error_callback):
		# Unpack the commands we've been supplied into a shell script.
		self.tempnam = tempfile.mkstemp()[1]

		fp = open(self.tempnam, 'w')
		# Prevent the script from continuing when one of the commands
		# fails. Because we want to abort in this situation.
		fp.write("\nset -xe\n")
		# From: http://stackoverflow.com/questions/821396/aborting-a-shell-script-if-any-command-returns-a-non-zero-value
		fp.write("set -o pipefail\n")

		for command in self.parameters['commands']:
			self.logger.info("Queuing command: %s", command)
			fp.write(command)
			fp.write("\n")

		fp.close()

		# CAUTION: This means the logger MUST be a job logger.
		# TODO: Handle this nicer...
		self.log_fp = self.logger.takeover_file()

		def completed_script(code):
			self.logger.untakeover_file(self.log_fp)
			self.logger.info("Shell prepare commands exited with: %d", code)
			# Remove the shell script.
			os.unlink(self.tempnam)
			#self.configuration.debug_cat_job_log(self.logger.job_id)
			if code == 0:
				callback("Successfully prepared via shell.")
			else:
				error_callback("Unable to prepare via shell.")

		# Start the commands off.
		command = ['bash', self.tempnam]
		self.scriptrunner = paasmaker.util.Popen(command,
			stdout=self.log_fp,
			stderr=self.log_fp,
			on_exit=completed_script,
			cwd=directory,
			io_loop=self.configuration.io_loop,
			env=environment)

	def _abort(self):
		# If signalled, abort the script runner and let it sort everything out.
		if hasattr(self, 'scriptrunner'):
			self.scriptrunner.kill()

class ShellPrepareTestTest(BasePrepareTest):
	def test_simple(self):
		logger = self.configuration.get_job_logger('testprepareshell')
		parameters = {
			'commands': [
				'echo "foo" > bar.txt',
				'cat -n bar.txt > sum.txt'
			]
		}

		self.registry.register(
			'paasmaker.prepare.shell',
			'paasmaker.pacemaker.prepare.shell.ShellPrepare',
			{},
			'Shell Prepare'
		)
		plugin = self.registry.instantiate(
			'paasmaker.prepare.shell',
			paasmaker.util.plugin.MODE.PREPARE_COMMAND,
			parameters,
			logger
		)

		# Proceed.
		plugin.prepare(os.environ, self.tempdir, self.success_callback, self.failure_callback)

		self.wait()

		self.assertTrue(self.success, "Did not prepare properly.")
		self.assertTrue(os.path.exists(os.path.join(self.tempdir, 'bar.txt')), "bar.txt does not exist.")
		self.assertTrue(os.path.exists(os.path.join(self.tempdir, 'sum.txt')), "sum.txt does not exist.")


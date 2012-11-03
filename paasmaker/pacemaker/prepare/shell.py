
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
	commands = colander.SchemaNode(colander.Sequence(), colander.SchemaNode(colander.String()), title="Commands")

class ShellPrepare(BasePrepare):
	MODES = [paasmaker.util.plugin.MODE.PREPARE_COMMAND]
	OPTIONS_SCHEMA = ShellPrepareConfigurationSchema()
	PARAMETERS_SCHEMA = ShellPrepareParametersSchema()

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
		extractor = paasmaker.util.Popen(command,
			stdout=self.log_fp,
			stderr=self.log_fp,
			on_exit=completed_script,
			cwd=directory,
			io_loop=self.configuration.io_loop,
			env=environment)

class ShellPrepareTestTest(BasePrepareTest):
	def test_simple(self):
		logger = self.configuration.get_job_logger('testprepareshell')
		parameters = {
			'commands': [
				'echo "foo" > bar.txt',
				'md5sum bar.txt > sum.txt'
			]
		}
		plugin = ShellPrepare(self.configuration, paasmaker.util.plugin.MODE.PREPARE_COMMAND, {}, parameters, logger=logger)

		# Sanity check.
		plugin.check_options()
		plugin.check_parameters()

		# Proceed.
		plugin.prepare(os.environ, self.tempdir, self.success_callback, self.failure_callback)

		self.wait()

		self.assertTrue(self.success, "Did not prepare properly.")
		self.assertTrue(os.path.exists(os.path.join(self.tempdir, 'bar.txt')), "bar.txt does not exist.")
		self.assertTrue(os.path.exists(os.path.join(self.tempdir, 'sum.txt')), "sum.txt does not exist.")
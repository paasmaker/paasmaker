
import os
import stat

from base import BaseSCM, BaseSCMTest, BaseSCMParametersSchema
import paasmaker

class DevDirectorySCM(BaseSCM):
	MODES = {
		paasmaker.util.plugin.MODE.SCM_EXPORT: BaseSCMParametersSchema(),
		paasmaker.util.plugin.MODE.SCM_FORM: None,
		paasmaker.util.plugin.MODE.STARTUP_ASYNC_PRELISTEN: None
	}

	def create_working_copy(self, callback, error_callback):
		directory = self.parameters['location']
		self.logger.info("Creating dev mode instance for directory %s" % directory)

		if not os.path.exists(directory):
			error_message = "Directory %s does not exist." % directory
			self.logger.error(error_message)
			error_callback(error_message)
			return

		callback(
			directory,
			"Successfully captured directory.",
			{
				'preferred_packer': 'devdirectory',
				'preferred_storer': 'devdirectory'
			}
		)

	def create_form(self, last_parameters):
		template = """
		<label for="parameters.location">Local Directory:</label>
		<input type="text" name="parameters.location" value="%(location)s" required="required" />
		"""

		return template % {
			'location': self._encoded_or_default(last_parameters, 'location', '')
		}

	def create_summary(self):
		return {
			'location': 'The local directory to use.'
		}

	def startup_async_prelisten(self, callback, error_callback):
		# Register other plugins and replacements needed to get this to work.
		self.configuration.plugins.register(
			'paasmaker.packer.devdirectory',
			'paasmaker.pacemaker.packer.devdirectory.DevDirectoryPacker',
			{},
			'Development Directory Packer'
		)
		self.configuration.plugins.register(
			'paasmaker.storer.devdirectory',
			'paasmaker.pacemaker.storer.devdirectory.DevDirectoryStorer',
			{},
			'Development Directory Storer'
		)
		self.configuration.plugins.register(
			'paasmaker.unpacker.devdirectory',
			'paasmaker.heart.unpacker.devdirectory.DevDirectoryUnpacker',
			{},
			'Development Directory Unpacker'
		)
		self.configuration.plugins.register(
			'paasmaker.fetcher.devdirectory',
			'paasmaker.heart.fetcher.devdirectory.DevDirectoryFetcher',
			{},
			'Development Directory Fetcher'
		)

		# Override two jobs in the system.
		self.configuration.plugins.register(
			'paasmaker.job.prepare.preparer',
			'paasmaker.pacemaker.scm.devdirectory.DevDirectorySourcePrepareJob',
			{},
			'Overridden Source Prepare Job for Development Directory SCM'
		)
		self.configuration.plugins.register(
			'paasmaker.job.heart.prestartup',
			'paasmaker.pacemaker.scm.devdirectory.DevDirectoryPreInstanceStartupJob',
			{},
			'Overridden Pre Instance Startup Job for Development Directory SCM'
		)

		# And we're done.
		callback("Completed adding additional plugins.")

# Replaced source preparer job, so as to not prepare dev-directory packages.
# TODO: In future, consider a way these jobs might be 'stacked'. But that might
# be overkill.
class DevDirectorySourcePrepareJob(paasmaker.common.job.prepare.SourcePreparerJob):
	def start_job(self, context):
		self.environment = context['environment']

		if 'preferred_packer' in context and context['preferred_packer'] == 'devdirectory':
			# This is being prepared for a devdirectory SCM.
			# Don't do the prepare tasks.
			message = "Not performing prepare tasks when using the devdirectory SCM."
			self.logger.info(message)
			self.done(message)
		else:
			# Do the normal thing.
			super(DevDirectorySourcePrepareJob, self).start_job(context)


class DevDirectoryPreInstanceStartupJob(paasmaker.common.job.heart.PreInstanceStartupJob):
	def _environment_ready(self, message):
		self.logger.info("Environment ready.")
		# Set an extra dev mode environment variable.
		self.instance_data['environment']['PM_DEV_MODE'] = 'True'
		# Save the instance data. Which now includes a mutated environment.
		self.configuration.instances.save()

		# Don't perform any startup tasks that we're supposed to.
		# (The default version of this plugin would do that).
		# Instead, write out a shell script that encapsulates all the environment
		# variables that we would have used, to allow you to run commands
		# locally that use the Paasmaker environment.

		formatted_variables = []
		for variable, value in self.instance_data['environment'].iteritems():
			formatted_variables.append('export %s="%s"' % (variable, value.replace('"', '\\"')))

		output_name = os.path.join(
			self.instance_path,
			'paasmaker_env_%s.sh' % self.instance_data['instance_type']['name']
		)

		fp = open(output_name, 'w')
		fp.write("#!/bin/bash\n")
		fp.write("# Environment for %s - created by Paasmaker on instance registration.\n" % self.instance_data['instance_type']['name'])
		fp.write("# Don't edit by hand. To recreate, you will need to deregister and re-register your instance.\n")
		fp.write("\n\n")
		fp.write("\n".join(formatted_variables))
		fp.write("\n\n")
		fp.write("$@\n")
		fp.write("\n")

		fp.close()

		# Make it executable.
		existing_mode = os.stat(output_name).st_mode
		os.chmod(output_name, existing_mode | stat.S_IEXEC)

		self.done("Not processing startup tasks - but has written a script out to capture the environment.")
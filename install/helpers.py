# Installation helpers.

import subprocess
import logging
import sys
import copy
import os

import constants

class InstallationError(Exception):
	"""
	An error raised when something goes wrong with the installation.
	"""
	pass

class InstallationContext(dict):
	"""
	An object to encapsulate settings and other context for the
	installation.
	"""
	def __init__(self, platform, subplatform, package_list, paasmaker_home):
		self['PLATFORM'] = platform
		self['SUBPLATFORM'] = subplatform

		self['PACKAGE_SETS'] = package_list[platform][subplatform]

		self['PAASMAKER_HOME'] = paasmaker_home

	def get_package_set(self, name):
		return self['PACKAGE_SETS'][name]

	def load_configuration(self, paths):
		# We don't import yaml until now, because
		# we might not have activated the virtualenv before this
		# function call.
		import yaml

		config = copy.deepcopy(constants.DEFAULT_INSTALLER_CONFIGURATION)

		for path in paths:
			if os.path.exists(path):
				user_config = yaml.safe_load(open(path, 'r'))
				config.update(user_config)

		self.update(config)

		# Set up or verify configuration.
		self._check_configuration()

	def _check_configuration(self):
		if self['use_system_openresty'] and not os.path.exists(self['openresty_binary']):
			raise InstallationError("Openresty path %s does not exist." % self['openresty_binary'])

		if self['use_system_redis'] and not os.path.exists(self['redis_binary']):
			raise InstallationError("Redis path %s does not exist." % self['redis_binary'])

def install_packages(context, packages):
	"""
	Install a system package. Raises an exception with a hopefully
	helpful error message if it's unable to perform it's work.

	This will switch to an appropriate package installation method
	for the platform that we're running on.

	:arg str platform: The platform we're installing on.
	:arg str subplatform: The sub platform we're installing on.
	:arg str package: The name of the package to install.
	"""
	if isinstance(packages, basestring):
		packages = [packages]

	if context['PLATFORM'] == constants.LINUX:
		if context['SUBPLATFORM'] == constants.UBUNTU:
			_install_packages_linux_ubuntu(context, packages)
		else:
			raise InstallationError("Unsupported platform.")
	else:
		raise InstallationError("Unsupported platform.")

def _install_packages_linux_ubuntu(context, packages):
	try:
		# This is to prevent apt-get from asking interactive
		# questions.
		# TODO: This doesn't work. Fix it.
		# See http://serverfault.com/questions/347937/how-do-i-ask-apt-get-to-skip-all-post-install-configuration-steps
		environment = copy.deepcopy(os.environ)
		environment['DEBIAN_FRONTEND'] = 'noninteractive'

		logging.info("About to install %s...", ",".join(packages))
		command = ['sudo', 'apt-get', '-y', 'install']
		command.extend(packages)
		subprocess.check_call(command, env=environment)

	except subprocess.CalledProcessError, ex:
		raise InstallationError(str(ex))

def enable_service(context, name):
	"""
	Enable the supplied system service.

	:arg dict context: The installation context.
	:arg str name: The name of the service.
	"""
	if context['PLATFORM'] == constants.LINUX:
		if context['SUBPLATFORM'] == constants.UBUNTU:
			_enable_service_linux_ubuntu(context, name)
		else:
			raise InstallationError("Unsupported platform.")
	else:
		raise InstallationError("Unsupported platform.")

def _enable_service_linux_ubuntu(context, name):
	generic_command(context, ['sudo', 'update-rc.d', name, 'defaults'])

def disable_service(context, name):
	"""
	Disable the supplied system service.

	:arg dict context: The installation context.
	:arg str name: The name of the service.
	"""
	if context['PLATFORM'] == constants.LINUX:
		if context['SUBPLATFORM'] == constants.UBUNTU:
			_disable_service_linux_ubuntu(context, name)
		else:
			raise InstallationError("Unsupported platform.")
	else:
		raise InstallationError("Unsupported platform.")

def _disable_service_linux_ubuntu(context, name):
	generic_command(context, ['sudo', 'update-rc.d', name, 'disable'])

def generic_command(context, command):
	"""
	Run a generic command as a subprocess.

	:arg list command: The command to run.
	"""
	try:
		logging.info("About to run %s ...", " ".join(command))
		subprocess.check_call(command)

	except subprocess.CalledProcessError, ex:
		raise InstallationError(str(ex))

def generic_command_shell(context, command):
	"""
	Run a generic command as a subprocess, with the shell
	enabled.

	Use ``generic_command`` in preference as it is safer
	with command line arguments, and drop back to this function
	when you can't easily achieve what you're trying to do.

	:arg str command: The command to run.
	"""
	try:
		logging.info("About to run %s ...", command)
		subprocess.check_call(command, shell=True)

	except subprocess.CalledProcessError, ex:
		raise InstallationError(str(ex))

def generic_builder(context, pre_path, instructions):
	"""
	Generic re-entrant fetch-source-code-unpack-and-build
	system. Very basic, but covers our use cases.

	:arg dict context: The installation context.
	:arg str pre_path: The path to unpack, install, and work in.
	:arg dict instructions: A dict containing the instructions
		on where to get the source package and how to build it.
	"""
	# Check to see if the binary exists.
	binary_path = os.path.join(pre_path, instructions['binary'])
	if os.path.exists(binary_path):
		logging.info("Already installed %s." % instructions['working_name'])
		return

	# Check the downloaded source file.
	source_package = os.path.join(pre_path, "%s.tar.gz" % instructions['working_name'])
	needs_download = False
	if not os.path.exists(source_package):
		needs_download = True
	else:
		# Check the checksum.
		checksum = subprocess.check_output(['sha1sum', source_package])
		checksum.split(" ")
		checksum = checksum[0]
		print "Checksum"
		print checksum
		print instructions['sha1']

		if checksum != instructions['sha1']:
			needs_download = True

	if needs_download:
		subprocess.check_call(['wget', '-O', source_package, '-c', instructions['url']])

	# Unpack it.
	unpacked_dir = os.path.join(pre_path, instructions['unpacked_name'])
	subprocess.check_call(['tar', 'zxvf', source_package, '-C', pre_path])

	# Configure it.
	if 'configure_command' in instructions:
		subprocess.check_call(instructions['configure_command'], cwd=unpacked_dir, shell=True)

	# Build it.
	subprocess.check_call(instructions['make_command'], cwd=unpacked_dir, shell=True)

	# Install it (if required).
	if 'install_command' in instructions:
		subprocess.check_call(instructions['install_command'], cwd=unpacked_dir, shell=True)
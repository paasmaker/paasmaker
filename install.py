#!/usr/bin/env python

#
# Paasmaker - Platform as a Service
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#

# Paasmaker Installation Script.

# Notes:
# * Currently supported platforms:
#   - Ubuntu Linux, 12.04.
#   - Darwin (Mac OSX) - only tested vs 10.8.
# * Why not use Chef, and Chef-Solo to do this instead? As this script
#   does quite a bit of what Chef does. It was decided at this stage
#   of development that Chef is slightly more advanced to install than
#   we would like for casual developers, so this script is easier for
#   people to use. It's designed to be scripted by Chef though. In the
#   future we hope to provide Chef recipes as well.

# Common imports.
import logging
import sys
import install
import os
import uuid
import subprocess
import copy
import tempfile
import getpass
import glob

if len(sys.argv) == 1:
	# No arguments.
	print "Usage: %s <configuration file>" % sys.argv[0]
	sys.exit(1)

# Set up logging.
logging.basicConfig(format='%(asctime)s %(levelname)s %(message)s', level=logging.INFO)

if getpass.getuser() == 'root':
	logging.error("Please do not run this script as root. Doing so is not currently supported.")
	sys.exit(1)

# Check our current directory. At this time we only currently
# support installing to the same directory as the files are stored.
paasmaker_home = os.path.dirname(os.path.abspath(__file__))
if paasmaker_home != os.getcwd():
	# Make the current directory the one where the script is.
	logging.info("Changing directory to %s", paasmaker_home)
	os.chdir(paasmaker_home)

# Figure out what platform we're on.
import platform

# Sanity check - what version of Python?
python_version = platform.python_version()

if python_version < '2.7' or python_version >= '2.8':
	logging.error("Sorry, only Python 2.7 is supported at this time.")
	sys.exit(1)

PLATFORM = platform.system()

# Figure out the sub platform, used to switch various things.
SUBPLATFORM = 'Generic'

platform_string = platform.platform()
if 'Ubuntu' in platform_string:
	SUBPLATFORM = 'Ubuntu'

if PLATFORM == install.constants.LINUX and SUBPLATFORM != install.constants.UBUNTU:
	logging.error("Sorry, your platform (%s, %s) is not supported at this time.", PLATFORM, SUBPLATFORM)
	logging.info("If you think your platform might work, you can remove this check from install.py and try again.")
	sys.exit(1)

logging.info("Found platform %s, sub platform %s.", PLATFORM, SUBPLATFORM)
logging.info("Installing core packages.")

# Set up the context object.
context = install.helpers.InstallationContext(
	PLATFORM,
	SUBPLATFORM,
	install.constants.SYSTEM_PACKAGES,
	paasmaker_home
)

# Get the core packages installed, so we can get pip and virtualenv up
# and running.
install.helpers.install_packages(context, context.get_package_set('core'))

# Now install virtualenv.
install.helpers.generic_command(context, ['sudo', 'pip', 'install', 'virtualenv'])

# Create a location for all our install things to go into.
if not os.path.exists("thirdparty"):
	os.mkdir("thirdparty")

# Create a new virtualenv environment.
# Only if we need to.
if not os.path.exists("thirdparty/python/bin/pip"):
	logging.info("Creating new virtual env.")
	install.helpers.generic_command(context, ['virtualenv', 'thirdparty/python'])
else:
	logging.info("virtualenv already exists.")

# Activate the environment now, inside this script.
logging.info("Activating virtualenv.")
bootstrap_script = "thirdparty/python/bin/activate_this.py"
execfile(bootstrap_script, dict(__file__=bootstrap_script))

# Now, install the other packages required via pip.
install.helpers.generic_command(context, ['pip', 'install', '-r', 'requirements.txt'])

# Now we can finally parse our command line arguments, and load
# a configuration file.
import argparse

parser = argparse.ArgumentParser()
parser.add_argument('configuration', help="The installation configuration file to use.")
parser.add_argument("--loglevel", default="INFO", help="Log level, one of DEBUG|INFO|WARNING|ERROR|CRITICAL.")

args = parser.parse_args()

# Reset the log level.
logging.debug("Resetting log level to %s.", args.loglevel)
logger = logging.getLogger()
logger.setLevel(getattr(logging, args.loglevel))

# Load the configuration file.
context.load_configuration([args.configuration])

# Install nginx and redis from source.
# Why from source?
# - nginx: we're using openresty, which contains additional patches required to
#   get the router to work.
# - redis: Ubuntu's version is 2.2 which is a bit old. We plan to use features
#   present in 2.6 in the near future.

if not context['use_system_redis']:
	install.helpers.generic_builder(context, "thirdparty", install.constants.REDIS)

if not context['use_system_openresty']:
	instructions = copy.deepcopy(install.constants.OPENRESTY)

	if context['PLATFORM'] == install.constants.DARWIN:
		# Figure out the correct pcre headers path - we want to use the homebrew
		# installed one, not the systems one - otherwise they conflict.
		# TODO: This is a bit hacky. Why not use the --json=v1 option? Because
		# that doesn't output the installed path - but just plain info does...
		raw_info = subprocess.check_output(['brew', 'info', 'pcre'])
		lines = raw_info.split("\n")
		for line in lines:
			# TODO: This assumes you installed homebrew under /usr. If not,
			# this will not work.
			if line.startswith("/usr"):
				bits = line.split(" ")
				path = bits[0]

				instructions['darwin_generic_configure_command'] = instructions['darwin_generic_configure_command'] % {'homebrew_pcre_path': path}

	install.helpers.generic_builder(context, "thirdparty", instructions)

# Install the various runtimes.
# RBENV
if context['runtime_rbenv_enable']:
	if context['PLATFORM'] == install.constants.DARWIN:
		# Just use homebrew's version.
		install.helpers.install_packages(context, ['rbenv', 'ruby-build'])
		rbenv_path = os.path.expanduser('~/.rbenv')
	else:
		# Is it already installed?
		rbenv_path = os.path.expanduser('~/.rbenv')
		if not context['runtime_rbenv_for_user']:
			# Install it into thirdparty/ instead.
			rbenv_path = 'thirdparty/rbenv'
		else:
			# See if they have RVM installed.
			# Exit with an error if they do and let
			# them decide what to do.
			if os.path.exists(os.path.expanduser('~/.rvm')):
				logging.error("You have RVM installed, and have selected to install rbenv for your user.")
				logging.error("You either need to disable this, or remove RVM.")

		if not os.path.exists(rbenv_path):
			# Need to install rbenv.
			# Install required packages.
			install.helpers.install_packages(context, context.get_package_set('runtime-rbenv'))

			# Now install rbenv.
			install.helpers.generic_command_shell(
				context,
				'git clone git://github.com/sstephenson/rbenv.git %s' % rbenv_path
			)
			install.helpers.generic_command_shell(
				context,
				'git clone git://github.com/sstephenson/ruby-build.git %s' % os.path.join(rbenv_path, 'plugins', 'ruby-build')
			)

	# If we're installing it for the user, update the bash profile.
	if context['runtime_rbenv_for_user']:
		if context['PLATFORM'] == install.constants.LINUX:
			bash_profile = open(os.path.expanduser('~/.profile'), 'r').read()
			if not 'export PATH="$HOME/.rbenv/bin:$PATH"' in bash_profile:
				install.helpers.generic_command_shell(
					context,
					'echo \'export PATH="$HOME/.rbenv/bin:$PATH"\' >> ~/.profile'
				)
			if not 'eval "$(rbenv init -)"' in bash_profile:
				install.helpers.generic_command_shell(
					context,
					'PATH="$HOME/.rbenv/bin:$PATH" echo \'eval "$(rbenv init -)"\' >> ~/.profile'
				)
		else:
			profile_path = os.path.expanduser('~/.bash_profile')
			if os.path.exists(profile_path):
				bash_profile = open(profile_path, 'r').read()
			else:
				bash_profile = ""

			if not 'eval "$(rbenv init -)"' in bash_profile:
				install.helpers.generic_command_shell(
					context,
					'PATH="$HOME/.rbenv/bin:$PATH" echo \'eval "$(rbenv init -)"\' >> %s' % profile_path
				)

	# Install any ruby versions we've been asked to install.
	if context['PLATFORM'] == install.constants.LINUX:
		rbenv_locator = 'export PATH="%s/bin:%s/shims:$PATH"' % (rbenv_path, rbenv_path)
	else:
		# For OSX, point the ruby binary at the correct location.
		# TODO: Fix this.
		rbenv_locator = 'export PATH="$HOME/.rbenv/shims:$PATH"'

	rbenv_current_versions = subprocess.check_output('%s; rbenv versions' % rbenv_locator, shell=True)

	rbenv_configure_options = ""
	if context['PLATFORM'] == install.constants.DARWIN:
		# See https://github.com/sstephenson/ruby-build/issues/285 and
		# https://github.com/sstephenson/ruby-build/issues/287 for this.
		# TODO: What are the ramifications of using this option?
		rbenv_configure_options = 'CFLAGS=-Wno-error=shorten-64-to-32'

	for version in context['runtime_rbenv_versions']:
		if version not in rbenv_current_versions:
			logging.info("Installing Ruby version %s. This will take a while; please be patient.", version)
			install.helpers.generic_command_shell(
				context,
				'%s; %s rbenv install --verbose %s' % (rbenv_locator, rbenv_configure_options, version)
			)
			# TODO: Figure out why the above command causes the install script to terminate.
			# On Linux/Ubuntu at least.
		else:
			logging.info("Ruby version %s is already installed.", version)

		# Ensure bundler is installed for this version.
		# This check runs every time you run the installer, to work
		# around where the installer gets terminated sometimes at the
		# end of the ruby compliation/installation.
		install.helpers.generic_command_shell(context, '%s; rbenv rehash' % rbenv_locator)
		rbenv_bundler = subprocess.check_output('%s; export RBENV_VERSION=%s; gem list' % (rbenv_locator, version), shell=True)
		if not 'bundler ' in rbenv_bundler:
			install.helpers.generic_command_shell(
				context,
				'%s; export RBENV_VERSION="%s"; rbenv rehash; gem install bundler; rbenv rehash' % (rbenv_locator, version)
			)

# NVM
if context['runtime_nvm_enable']:
	nvm_path = os.path.expanduser('~/.nvm')
	if not context['runtime_nvm_for_user']:
		# Install to a local directory just for Paasmaker.
		nvm_path = "thirdparty/nvm"

	if not os.path.exists(nvm_path):
		# Install it.
		if context['runtime_nvm_for_user']:
			# If installing for the user, use the supplied install script,
			# as that does all the profile/bashrc lifting.
			install.helpers.generic_command_shell(
				context,
				"curl https://raw.github.com/creationix/nvm/master/install.sh | sh"
			)
		else:
			# Just clone the repo into the path.
			install.helpers.generic_command(
				context,
				['git', 'clone', 'git://github.com/creationix/nvm.git', nvm_path]
			)

	# Install any versions requested.
	nvm_script = os.path.join(nvm_path, "nvm.sh")

	# Get the current versions from the filesystem.
	current_versions = set()
	for path in glob.glob(os.path.join(nvm_path, 'v*')):
		current_versions.add(os.path.basename(path))

	for version in context['runtime_nvm_versions']:
		if version not in current_versions:
			install.helpers.generic_command_shell(
				context,
				'bash -c ". %s; nvm install %s"' % (nvm_script, version)
			)
		# TODO: Hack to install handlebars so that the --debug=1 mode works.
		if version == 'v0.8.22':
			logger.info("Installing handlebars to compile JavaScript templates in debug mode.")
			npm_list = subprocess.check_output('bash -c ". %s; nvm use v0.8.22; npm list -g"' % nvm_script, shell=True)
			if ' handlebars@' not in npm_list:
				install.helpers.generic_command_shell(
					context,
					'bash -c ". %s; nvm use v0.8.22; npm install handlebars -g"' % nvm_script
				)


# PHP / Static runtime.
if context['runtime_php_enable']:
	# To enable, all we really need to do is install Apache and some PHP packages.
	install.helpers.install_packages(context, context.get_package_set('runtime-php'))
	if len(context['runtime_php_extra_packages']) > 0:
		install.helpers.install_packages(context, context['runtime_php_extra_packages'])

	if context['PLATFORM'] == install.constants.LINUX:
		for module in context['runtime_php_apache_modules']:
			install.helpers.generic_command(context, ['sudo', 'a2enmod', module])

	if context['runtime_php_disable_system_apache']:
		install.helpers.disable_service(context, 'apache2')

# Services.
if context['service_managedmysql_enable']:
	install.helpers.install_packages(context, context.get_package_set('service-mysql'))

	# On Linux, fix up AppArmor profiles.
	if context['PLATFORM'] == install.constants.LINUX:
		apparmor_control = "/etc/apparmor.d/local/usr.sbin.mysqld"
		if os.path.exists(apparmor_control):
			search_token = os.path.join(paasmaker_home, "scratch")

			contents = open(apparmor_control, 'r').read()
			if search_token not in contents:
				logger.info("Updating AppArmor local profile for MySQL.")

				temp_file = tempfile.NamedTemporaryFile(delete=False)
				temp_file.write(contents)
				temp_file.write("  ")
				temp_file.write(search_token)
				temp_file.write('/ r,\n')
				temp_file.write("  ")
				temp_file.write(search_token)
				temp_file.write('/** rwk,\n')

				# Move that temp file into place with sudo.
				install.helpers.generic_command(context, ['sudo', 'mv', temp_file.name, apparmor_control])

				install.helpers.generic_command(context, ['sudo', 'service', 'apparmor', 'reload'])

if context['service_managedpostgres_enable']:
	install.helpers.install_packages(context, context.get_package_set('service-postgres'))

if context['service_managedmongodb_enable']:
	install.helpers.install_packages(context, context.get_package_set('service-mongodb'))

if not context['write_paasmaker_configuration']:
	# We've been asked not to tamper with the paasmaker.yml configuration file.
	# Respect that.
	logging.info("Configuration has asked us not to write the configuration file.")
	sys.exit(0)

# Write out the configuration file.
# Merge in with any configuration file found, rather than overwriting.
# (This allows the install script to be used to update things.)

logging.info("Updating or writing configuration file.")

# Import yaml now, not earlier, because we were not in the virtualenv.
import yaml

configuration = copy.deepcopy(install.constants.DEFAULT_PAASMAKER_CONFIGURATION)
if os.path.exists('paasmaker.yml'):
	configuration = yaml.safe_load(open('paasmaker.yml', 'r'))

# Now, update the configuration as we need to.
configuration['heart']['enabled'] = context['is_heart']
configuration['router']['enabled'] = context['is_router']
configuration['pacemaker']['enabled'] = context['is_pacemaker']

configuration['redis_binary'] = context['redis_binary']
configuration['nginx_binary'] = context['openresty_binary']

configuration['master']['host'] = context['master_node']
configuration['master']['port'] = context['master_port']

configuration['heart']['shutdown_on_exit'] = context['shutdown_daemons_on_exit']

if context['my_name'] is not None:
	configuration['my_name'] = context['my_name']
if context['my_route'] is not None:
	configuration['my_route'] = context['my_route']

if context['node_token'] is None and ('node_token' not in configuration or configuration['node_token'] is None):
	# Generate a new node token.
	node_token = str(uuid.uuid4())
	configuration['node_token'] = node_token
if context['node_token'] is not None:
	# Set the node token as supplied. This is for secondary nodes.
	configuration['node_token'] = context['node_token']

if configuration['pacemaker']['enabled'] and context['super_token'] is None and ('super_token' not in configuration['pacemaker'] or configuration['pacemaker']['super_token'] == 'not-applicable'):
	# Generate a new super token.
	super_token = str(uuid.uuid4())
	configuration['pacemaker']['super_token'] = super_token

if configuration['pacemaker']['enabled']:
	# Always set the cluster hostname from the installation configuration file.
	configuration['pacemaker']['cluster_hostname'] = context['cluster_hostname']

if configuration['pacemaker']['enabled']:
	if context['init_redirect_port80']:
		configuration['pacemaker']['frontend_domain_postfix'] = ''
	else:
		configuration['pacemaker']['frontend_domain_postfix'] = context['frontend_domain_postfix']

configuration['router']['nginx']['shutdown'] = context['shutdown_daemons_on_exit']

if context['redis_mode'] == 'completely-managed':
	configuration['redis'] = copy.deepcopy(install.constants.DEFAULT_PAASMAKER_MANAGED_REDIS)

elif context['redis_mode'] == 'defer-to-master':
	configuration['redis'] = copy.deepcopy(install.constants.DEFAULT_PAASMAKER_MANAGED_REDIS)

	configuration['redis']['table']['host'] = context['master_node']
	configuration['redis']['table']['managed'] = False
	configuration['redis']['stats']['host'] = context['master_node']
	configuration['redis']['stats']['managed'] = False
	configuration['redis']['jobs']['host'] = context['master_node']
	configuration['redis']['jobs']['managed'] = False

	if configuration['router']['enabled']:
		# Also slave off the master.
		configuration['redis']['slaveof'] = {
			'enabled': True,
			'host': context['master_node'],
			'port': 42510
		}
		# Reset the table to listen locally.
		configuration['redis']['table']['host'] = '0.0.0.0'
		configuration['redis']['table']['managed'] = True

# Toggle the shutdown flag.
configuration['redis']['table']['shutdown'] = context['shutdown_daemons_on_exit']
configuration['redis']['stats']['shutdown'] = context['shutdown_daemons_on_exit']
configuration['redis']['jobs']['shutdown'] = context['shutdown_daemons_on_exit']

def enable_plugin(conf, plugin):
	plugin_name = plugin['name']

	# Disable it first.
	disable_plugin(conf, plugin)

	# Then add it to the list.
	conf.append(plugin)

def disable_plugin(conf, plugin):
	plugin_name = plugin['name']
	for i in range(len(conf)):
		entry = conf[i]
		if entry['name'] == plugin_name:
			# Remove this index.
			# TODO: If it's twice in the file (invalid anyway!)
			# this won't detect and remove the subsequent ones.
			del conf[i]
			return

if context['runtime_rbenv_enable']:
	enable_plugin(
		configuration['plugins'],
		{
			'name': 'paasmaker.runtime.ruby.rbenv',
			'class': 'paasmaker.heart.runtime.rbenv.RbenvRuntime',
			'title': 'Ruby (rbenv) Runtime',
			'parameters': {
				'rbenv_path': rbenv_path
			}
		}
	)

if context['runtime_nvm_enable']:
	enable_plugin(
		configuration['plugins'],
		{
			'name': 'paasmaker.runtime.node.nvm',
			'class': 'paasmaker.heart.runtime.nvm.NvmRuntime',
			'title': 'Nodejs (nvm) Runtime',
			'parameters': {
				'nvm_path': nvm_path
			}
		}
	)

if context['runtime_php_enable']:
	enable_plugin(
		configuration['plugins'],
		{
			'name': 'paasmaker.runtime.php',
			'class': 'paasmaker.heart.runtime.php.PHPRuntime',
			'title': 'PHP Runtime',
			'parameters': {
				'managed': True,
				'shutdown': context['shutdown_daemons_on_exit']
			}
		}
	)

	# This also enables the static plugin, as they're basically the
	# same.
	enable_plugin(
		configuration['plugins'],
		{
			'name': 'paasmaker.runtime.static',
			'class': 'paasmaker.heart.runtime.static.StaticRuntime',
			'title': 'Static Files Runtime',
			'parameters': {
				'managed': True,
				'shutdown': context['shutdown_daemons_on_exit']
			}
		}
	)

if context['runtime_shell_enable']:
	enable_plugin(
		configuration['plugins'],
		{
			'name': 'paasmaker.runtime.shell',
			'class': 'paasmaker.heart.runtime.shell.ShellRuntime',
			'title': 'Shell Runtime'
		}
	)

if context['service_managedmysql_disable_system_mysql']:
	install.helpers.disable_service(context, 'mysql')
if context['service_managedmysql_disable_system_postgres']:
	install.helpers.disable_service(context, 'postgresql')
if context['service_managedmongodb_disable_system_mongodb']:
	install.helpers.disable_service(context, 'mongodb')

if context['service_managedpostgres_enable']:
	enable_plugin(
		configuration['plugins'],
		{
			'name': 'paasmaker.service.postgres',
			'class': 'paasmaker.pacemaker.service.managedpostgres.ManagedPostgresService',
			'title': 'Managed Postgres Service',
			'parameters': {
				'root_password': 'paasmaker',
				'shutdown': context['shutdown_daemons_on_exit']
			}
		}
	)

if context['service_managedmysql_enable']:
	enable_plugin(
		configuration['plugins'],
		{
			'name': 'paasmaker.service.mysql',
			'class': 'paasmaker.pacemaker.service.managedmysql.ManagedMySQLService',
			'title': 'Managed MySQL Service',
			'parameters': {
				'root_password': 'paasmaker',
				'shutdown': context['shutdown_daemons_on_exit']
			}
		}
	)

if context['service_managedmongodb_enable']:
	enable_plugin(
		configuration['plugins'],
		{
			'name': 'paasmaker.service.managedmongodb',
			'class': 'paasmaker.pacemaker.service.managedmongodb.ManagedMongoService',
			'title': 'Managed Mongodb Service',
			'parameters': {
				'shutdown': context['shutdown_daemons_on_exit']
			}
		}
	)

if context['service_managedredis_enable']:
	enable_plugin(
		configuration['plugins'],
		{
			'name': 'paasmaker.service.managedredis',
			'class': 'paasmaker.pacemaker.service.managedredis.ManagedRedisService',
			'title': 'Managed Redis Service',
			'parameters': {
				'shutdown': context['shutdown_daemons_on_exit']
			}
		}
	)

for plugin in context['extra_plugins']:
	enable_plugin(configuration['plugins'], plugin)

# Write out the configuration file.
serialized = yaml.safe_dump(configuration, default_flow_style=False)

serialized = """# Generated configuration file for Paasmaker.
# If you edit this file, the next time you run the install script,
# it will merge any changes with your configuration.
# However, any comments that you added to this file will be lost.

# NOTE: The following values will be overwritten from the installation
# configuration if you re-run the installer. These are overwritten
# regardless of their setting in paasmaker.yml:
#
#  pacemaker.cluster_hostname
#  pacemaker.frontend_domain_postfix
#  my_name
#  my_route
#  master.host
#  master.port
#  heart.enabled
#  router.enabled
#  pacemaker.enabled
#  redis_binary
#  nginx_binary
#  node_token
#  Any 'shutdown' flags.
#
# node_token, super_token are preserved and not regenerated
# after the first install run (as applicable).

""" + serialized

open('paasmaker.yml', 'w').write(serialized)

logging.info("Completed writing out configuration file.")

if context['install_init_script']:
	init_script_body = install.constants.INIT_SCRIPT % {
		'paasmaker_home': paasmaker_home,
		'enable_iptables': context['init_redirect_port80'],
		'paasmaker_user': getpass.getuser()
	}

	init_script_path = '/etc/init.d/paasmaker'

	temp_file = tempfile.NamedTemporaryFile(delete=False)
	temp_file.write(init_script_body)

	# Move that temp file into place with sudo.
	install.helpers.generic_command(context, ['sudo', 'mv', temp_file.name, init_script_path])
	install.helpers.generic_command(context, ['sudo', 'chmod', '755', init_script_path])

if context['enable_init_script']:
	install.helpers.enable_service(context, 'paasmaker')

print
print
print
print

print "Paasmaker is now installed!"
if context['enable_init_script']:
	print "To start, run sudo /etc/init.d/paasmaker start"
else:
	print "To start, run ./pm-server.py"
	print "And then visit http://pacemaker.local.paasmaker.net:42530 in your web browser."
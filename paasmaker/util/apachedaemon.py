#
# Paasmaker - Platform as a Service
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#

import os
import signal
import shutil
import tempfile
import logging
import subprocess
import time
import unittest
from distutils.spawn import find_executable
import platform

import paasmaker
from ..common.testhelpers import TestHelpers
from manageddaemon import ManagedDaemon, ManagedDaemonError

import tornado.testing
import tornadoredis

class ApacheDaemonError(ManagedDaemonError):
	pass

class ApacheDaemon(ManagedDaemon):
	"""
	A managed Apache instance. Runs an Apache server
	with a cut down configuration file.

	Note that the server uses the system's module
	configuration - eg, the contents of /etc/apache2/mods-enabled/
	on Ubuntu systems - so the started Apache will mirror that setup.
	However, all other configuration is seperate.
	"""

	# This configuration is based on the Debian default configuration,
	# but cut down significantly.
	# TODO: NOTE: It uses the system's module configuration for PHP
	# and so forth to make it easier to configure and customize. We do
	# not however include the contents of conf.d/.
	CONFIGURATION = """
ServerRoot "%(server_root)s"
LockFile %(server_root)s/accept.lock
PidFile %(server_root)s/apache2.pid

%(platform_darwin)s

Timeout 300
KeepAlive On
MaxKeepAliveRequests 100
# This is lower than the default.
KeepAliveTimeout 5

# You will need to set your system up to the use the prefork module,
# because that's the one compatible with PHP.
<IfModule mpm_prefork_module>
    StartServers          5
    MinSpareServers       5
    MaxSpareServers      10
    MaxClients          150
    MaxRequestsPerChild   0
</IfModule>

AccessFileName .htaccess
<Files ~ "^\.ht">
    Order allow,deny
    Deny from all
    Satisfy all
</Files>
DefaultType text/plain
HostnameLookups Off
ErrorLog %(server_root)s/error.log
LogLevel warn
%(platform_ubuntu)s

NameVirtualHost *:%(port)d
Listen %(port)d

# And this is where it includes configuration from.
Include %(config_file_dir)s/

# TODO: Fix these log lines - they're causing startup errors.
#LogFormat "%%v:%%p %%h %%l %%u %%t \"%%r\" %%>s %%O \"%%{Referer}i\" \"%%{User-Agent}i\"" vhost_combined
#LogFormat "%%h %%l %%u %%t \"%%r\" %%>s %%O \"%%{Referer}i\" \"%%{User-Agent}i\"" combined
#LogFormat "%%h %%l %%u %%t \"%%r\" %%>s %%O" common
#LogFormat "%%{Referer}i -> %%U" referer
#LogFormat "%%{User-agent}i" agent
"""

	PLATFORM_UBUNTU = """
Include /etc/apache2/mods-enabled/*.load
Include /etc/apache2/mods-enabled/*.conf
"""

	PLATFORM_DARWIN = """
LoadModule authn_file_module /usr/libexec/apache2/mod_authn_file.so
LoadModule authn_anon_module /usr/libexec/apache2/mod_authn_anon.so
LoadModule authn_default_module /usr/libexec/apache2/mod_authn_default.so
LoadModule authz_host_module /usr/libexec/apache2/mod_authz_host.so
LoadModule authz_groupfile_module /usr/libexec/apache2/mod_authz_groupfile.so
LoadModule authz_user_module /usr/libexec/apache2/mod_authz_user.so
LoadModule authz_owner_module /usr/libexec/apache2/mod_authz_owner.so
LoadModule authz_default_module /usr/libexec/apache2/mod_authz_default.so
LoadModule auth_basic_module /usr/libexec/apache2/mod_auth_basic.so
LoadModule auth_digest_module /usr/libexec/apache2/mod_auth_digest.so
LoadModule include_module /usr/libexec/apache2/mod_include.so
LoadModule deflate_module /usr/libexec/apache2/mod_deflate.so
LoadModule env_module /usr/libexec/apache2/mod_env.so
LoadModule mime_magic_module /usr/libexec/apache2/mod_mime_magic.so
LoadModule expires_module /usr/libexec/apache2/mod_expires.so
LoadModule headers_module /usr/libexec/apache2/mod_headers.so
LoadModule setenvif_module /usr/libexec/apache2/mod_setenvif.so
LoadModule ssl_module /usr/libexec/apache2/mod_ssl.so
LoadModule mime_module /usr/libexec/apache2/mod_mime.so
LoadModule status_module /usr/libexec/apache2/mod_status.so
LoadModule autoindex_module /usr/libexec/apache2/mod_autoindex.so
LoadModule vhost_alias_module /usr/libexec/apache2/mod_vhost_alias.so
LoadModule negotiation_module /usr/libexec/apache2/mod_negotiation.so
LoadModule dir_module /usr/libexec/apache2/mod_dir.so
LoadModule alias_module /usr/libexec/apache2/mod_alias.so
LoadModule rewrite_module /usr/libexec/apache2/mod_rewrite.so
LoadModule php5_module /usr/libexec/apache2/libphp5.so

<IfModule mod_php5.c>
    <FilesMatch "\.ph(p3?|tml)$">
        SetHandler application/x-httpd-php
    </FilesMatch>
    <FilesMatch "\.phps$">
        SetHandler application/x-httpd-php-source
    </FilesMatch>
    # To re-enable php in user directories comment the following lines
    # (from <IfModule ...> to </IfModule>.) Do NOT set it to On as it
    # prevents .htaccess files from disabling it.
    <IfModule mod_userdir.c>
        <Directory /home/*/public_html>
            php_admin_value engine Off
        </Directory>
    </IfModule>
</IfModule>
"""

	def configure(self, working_dir, port):
		"""
		Configure this instance.

		:arg str working_dir: The working directory.
		:arg int port: The port to listen on.
		"""
		self.parameters['working_dir'] = working_dir
		self.parameters['port'] = port

		# Create the working dir. If this fails, let it bubble up.
		if not os.path.exists(working_dir):
			os.makedirs(working_dir)

		# And create a directory for configuration files.
		config_file_dir = os.path.join(working_dir, 'configuration')
		if not os.path.exists(config_file_dir):
			os.makedirs(config_file_dir)

		self.parameters['config_file_dir'] = config_file_dir

		self.save_parameters()

	def get_pid_path(self):
		return os.path.join(self.parameters['working_dir'], 'apache2.pid')

	def _get_binary_path(self):
		# Short circuit for Ubuntu systems.
		if os.path.exists('/usr/sbin/apache2'):
			return '/usr/sbin/apache2'

		binary = find_executable("apache2")
		if not binary:
			binary = find_executable("httpd")

		if not binary:
			raise ValueError("Can't find installation of apache - looked for apache2 and httpd.")

		return binary

	def start(self, callback, error_callback):
		"""
		Start up the server for this instance.
		"""
		# Write out the configuration.
		configfile = self.get_configuration_path(self.parameters['working_dir'])
		parameters = {}
		parameters['port'] = self.parameters['port']
		parameters['server_root'] = self.parameters['working_dir']
		parameters['config_file_dir'] = self.parameters['config_file_dir']
		parameters['platform_darwin'] = ''
		parameters['platform_ubuntu'] = ''
		if platform.system() == 'Darwin':
			parameters['platform_darwin'] = self.PLATFORM_DARWIN
		if platform.system() == 'Linux' and 'Ubuntu' in platform.platform():
			parameters['platform_ubuntu'] = self.PLATFORM_UBUNTU
		# TODO: Support Centos.

		configuration = self.CONFIGURATION % parameters
		#print configuration

		fp = open(configfile, 'w')
		fp.write(configuration)
		fp.close()

		# Fire up the server.
		# For debugging, you might like to comment out the stderr redirection.
		logging.info("Starting up apache2 server on port %d." % self.parameters['port'])
		binary = self._get_binary_path()
		# TODO: The output isn't captured here, because otherwise
		# debugging is too hard. Fix this in the future - the CalledProcessError
		# doesn't have an output attribute that we can read, even if we switch
		# check_call() for check_output() (as per the documentation).
		subprocess.check_call(
			[
				binary,
				'-f',
				configfile,
				'-k',
				'start'
			]
		)

		# Wait for the port to come into use.
		self.configuration.port_allocator.wait_until_port_used(
			self.configuration.io_loop,
			self.parameters['port'],
			5,
			callback,
			error_callback
		)

	def is_running(self, keyword=None):
		binary = self._get_binary_path()
		binary = os.path.basename(binary)
		return super(ApacheDaemon, self).is_running(binary)

	def destroy(self):
		"""
		Destroy this instance of apache2, removing all generated data.
		"""
		self.stop()
		shutil.rmtree(self.parameters['working_dir'])

	def get_config_dir(self):
		return self.parameters['config_file_dir']

	def graceful(self):
		"""
		Perform a graceful restart of this Apache instance.

		This works by calling the 'graceful' command. It will
		return basically immediately on success, or raise an
		exception on failure.
		"""
		# Perform a graceful restart of the server.
		# TODO: Make this call Async.
		configfile = self.get_configuration_path(self.parameters['working_dir'])
		binary = self._get_binary_path()
		output = subprocess.check_output(
			[
				binary,
				'-f',
				configfile,
				'-k',
				'graceful'
			],
			stderr=subprocess.STDOUT
		)

		return output

class ApacheDaemonTest(tornado.testing.AsyncTestCase, TestHelpers):
	def setUp(self):
		super(ApacheDaemonTest, self).setUp()
		self.configuration = paasmaker.common.configuration.ConfigurationStub(0, [], io_loop=self.io_loop)

	def tearDown(self):
		if hasattr(self, 'server'):
			self.server.destroy()
		self.configuration.cleanup()
		super(ApacheDaemonTest, self).tearDown()
		pass

	def test_basic(self):
		self.server = ApacheDaemon(self.configuration)
		port = self.configuration.get_free_port()
		self.server.configure(
			self.configuration.get_scratch_path_exists('apache2'),
			port
		)
		self.server.start(self.stop, self.stop)
		result = self.wait()

		self.assertIn("In appropriate state", result, "Failed to start apache server.")

		# Connect to it. It should give us a 404 error.
		request = tornado.httpclient.HTTPRequest('http://localhost:%d/foo' % port)
		client = tornado.httpclient.AsyncHTTPClient(io_loop=self.io_loop)
		client.fetch(request, self.stop)

		response = self.wait()
		self.assertEquals(response.code, 404, "Wrong response code.")
		self.assertTrue(len(response.body) > 0, "Didn't return a body.")

		self.server.is_running()

		self.server.stop()

		# Give it a little time to stop.
		time.sleep(0.1)
		self.assertFalse(self.server.is_running())

		# Start it again.
		self.server.start(self.stop, self.stop)
		result = self.wait()

		self.assertIn("In appropriate state", result, "Failed to start apache2 server.")

		self.assertTrue(self.server.is_running())

		# Graceful the server.
		self.server.graceful()
		time.sleep(0.1)

		# Make sure it's still listening.
		request = tornado.httpclient.HTTPRequest('http://localhost:%d/foo' % port)
		client = tornado.httpclient.AsyncHTTPClient(io_loop=self.io_loop)
		client.fetch(request, self.stop)

		response = self.wait()
		self.assertEquals(response.code, 404, "Wrong response code.")
		self.assertTrue(len(response.body) > 0, "Didn't return a body.")

		# Also make sure it's still running.
		self.assertTrue(self.server.is_running())
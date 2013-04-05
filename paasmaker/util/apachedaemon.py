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

	def configure(self, working_dir, port, callback, error_callback):
		"""
		Configure this instance.

		:arg str working_dir: The working directory.
		:arg int port: The port to listen on.
		:arg callable callback: The callback to call when done.
		:arg callable error_callback: The callback to call on error.
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

		callback("Configured Apache.")

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

		def process_forked(code):
			if code == 0:
				# Wait for the port to come into use.
				logging.info("Apache2 started, waiting for listening state.")
				self._wait_until_port_inuse(
					self.parameters['port'],
					callback,
					error_callback
				)
			else:
				error_message = "Unable to start Apache2 - exited with error code %d." % code
				error_message += "\nOutput:\n" + self._fetch_output()
				logging.error(error_message)
				error_callback(error_message)

		# Fire up the server.
		logging.info("Starting up Apache2 server on port %d." % self.parameters['port'])
		try:
			binary = self._get_binary_path()
			paasmaker.util.popen.Popen(
				[
					binary,
					'-f',
					configfile,
					'-k',
					'start'
				],
				redirect_stderr=True,
				on_stdout=self._fetchable_output,
				on_exit=process_forked,
				io_loop=self.configuration.io_loop
			)
		except OSError, ex:
			logging.error(ex)
			error_callback(str(ex), exception=ex)

	def is_running(self, keyword=None):
		binary = self._get_binary_path()
		binary = os.path.basename(binary)
		return super(ApacheDaemon, self).is_running(binary)

	def destroy(self, callback, error_callback):
		"""
		Destroy this instance of apache2, removing all generated data.
		"""
		def stopped(message):
			# Delete all the files.
			shutil.rmtree(self.parameters['working_dir'])
			callback(message)

		self.stop(stopped, error_callback)

	def get_config_dir(self):
		return self.parameters['config_file_dir']

	def graceful(self, callback, error_callback):
		"""
		Perform a graceful restart of this Apache instance.

		This works by calling the 'graceful' command.
		"""
		# Perform a graceful restart of the server.
		configfile = self.get_configuration_path(self.parameters['working_dir'])
		binary = self._get_binary_path()

		def graceful_applied(code):
			if code == 0:
				callback("Successfully gracefulled.")
			else:
				error_message = "Unable to graceful Apache - exited with error code %d." % code
				error_message += "Output:\n" + self._fetch_output()
				logging.error(error_message)
				error_callback(error_message)

		try:
			paasmaker.util.popen.Popen(
				[
					binary,
					'-f',
					configfile,
					'-k',
					'graceful'
				],
				redirect_stderr=True,
				on_stdout=self._fetchable_output,
				on_exit=graceful_applied,
				io_loop=self.configuration.io_loop
			)
		except OSError, ex:
			logging.error(ex)
			error_callback(str(ex), exception=ex)

	def get_error_log(self):
		return open(os.path.join(self.parameters['working_dir'], 'error.log'), 'r').read()

class ApacheDaemonTest(tornado.testing.AsyncTestCase, TestHelpers):
	def setUp(self):
		super(ApacheDaemonTest, self).setUp()
		self.configuration = paasmaker.common.configuration.ConfigurationStub(0, [], io_loop=self.io_loop)

	def tearDown(self):
		if hasattr(self, 'server'):
			self.server.destroy(self.stop, self.stop)
			self.wait()
		self.configuration.cleanup(self.stop, self.stop)
		self.wait()
		super(ApacheDaemonTest, self).tearDown()
		pass

	def test_basic(self):
		self.server = ApacheDaemon(self.configuration)
		port = self.configuration.get_free_port()
		self.server.configure(
			self.configuration.get_scratch_path_exists('apache2'),
			port,
			self.stop,
			self.stop
		)
		self.wait()
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

		self.server.stop(self.stop, self.stop)
		self.wait()

		# Give it a little time to stop.
		time.sleep(0.1)
		self.assertFalse(self.server.is_running())

		# Start it again.
		self.server.start(self.stop, self.stop)
		result = self.wait()

		self.assertIn("In appropriate state", result, "Failed to start apache2 server.")

		self.assertTrue(self.server.is_running())

		# Graceful the server.
		self.server.graceful(self.stop, self.stop)
		self.wait()

		# Make sure it's still listening.
		request = tornado.httpclient.HTTPRequest('http://localhost:%d/foo' % port)
		client = tornado.httpclient.AsyncHTTPClient(io_loop=self.io_loop)
		client.fetch(request, self.stop)

		response = self.wait()
		self.assertEquals(response.code, 404, "Wrong response code.")
		self.assertTrue(len(response.body) > 0, "Didn't return a body.")

		# Also make sure it's still running.
		self.assertTrue(self.server.is_running())
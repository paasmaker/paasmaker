#
# Paasmaker - Platform as a Service
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#

import unittest
import os
import signal
import logging
import tempfile
import uuid
import shutil
import hashlib
import logging
import subprocess

import tornado
import yaml

import configuration
import paasmaker

from pubsub import pub

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

class ConfigurationStub(configuration.Configuration):
    """
    A test version of the configuration object, for unit tests.

    This class can handle generating a default configuration, using
    temporary paths, and behaves just like the normal Configuration object -
    except that it can also clean up after itself once the unit test is complete.
    """

    default_config = """
# The port to this test instance is the master port, for testing purposes.
http_port: %(master_port)d
node_token: %(node_token)s
scratch_directory: %(scratch_dir)s
master:
  host: localhost
  port: %(master_port)d

misc_ports:
  minimum: 42700
  maximum: 42799

redis:
  table:
    host: 0.0.0.0
    port: %(router_table_port)d
    managed: true
  # slaveof:
  #   enabled: true
  #   host: localhost
  #   port: 1234
  stats:
    host: 0.0.0.0
    port: %(router_stats_port)d
    managed: true
  jobs:
    host: 0.0.0.0
    port: %(jobs_port)d
    managed: true

plugins:
  - name: paasmaker.service.parameters
    class: paasmaker.pacemaker.service.parameters.ParametersService
    title: Parameters Service
  - name: paasmaker.scm.zip
    class: paasmaker.pacemaker.scm.zip.ZipSCM
    title: Zip file SCM
  - name: paasmaker.prepare.shell
    class: paasmaker.pacemaker.prepare.shell.ShellPrepare
    title: Shell preparer
  - name: paasmaker.runtime.shell
    class: paasmaker.heart.runtime.ShellRuntime
    title: Shell Runtime
  - name: paasmaker.auth.internal
    class: paasmaker.pacemaker.auth.internal.InternalAuth
    title: Internal Authentication

  - name: paasmaker.runtime.php
    class: paasmaker.heart.runtime.PHPRuntime
    title: PHP
  - name: paasmaker.startup.shell
    class: paasmaker.pacemaker.prepare.shell.ShellPrepare
    title: Shell startup
  - name: paasmaker.runtime.shell
    class: paasmaker.heart.runtime.ShellRuntime
    title: Shell Runtime
  - name: paasmaker.scmlist.dummy
    class: paasmaker.pacemaker.controller.scmlist.DummySCMList
    title: Dummy SCM lister
"""

    pacemaker_config = """
pacemaker:
  enabled: true
  super_token: %(super_token)s
  allow_supertoken: true
  dsn: "sqlite:///:memory:"
  cluster_hostname: local.paasmaker.net
  scmlisters:
    - for: paasmaker.scm.zip
      plugins:
        - paasmaker.scmlist.dummy
"""

    heart_config = """
heart:
  enabled: true
"""

    router_config = """
router:
  enabled: true
  stats_log: %(stats_log)s
"""

    def __init__(self, port=42600, modules=[], io_loop=None):
        # Choose filenames and set up example configuration.
        configfile = tempfile.mkstemp()
        self.params = {}

        allocator = paasmaker.util.port.FreePortFinder()

        self.params['node_token'] = str(uuid.uuid4())
        self.params['super_token'] = str(uuid.uuid4())
        self.params['scratch_dir'] = tempfile.mkdtemp()
        self.params['master_port'] = port
        self.params['router_table_port'] = allocator.free_in_range(42710, 42799)
        self.params['router_stats_port'] = allocator.free_in_range(42710, 42799)
        self.params['jobs_port'] = allocator.free_in_range(42710, 42799)
        self.params['broker_port'] = allocator.free_in_range(42710, 42799)
        self.params['stats_log'] = "%s/access.log.paasmaker" % self.params['scratch_dir']

        # Create the configuration file.
        configuration = self.default_config % self.params

        if 'pacemaker' in modules:
            configuration += self.pacemaker_config % self.params
        if 'heart' in modules:
            configuration += self.heart_config % self.params
        if 'router' in modules:
            configuration += self.router_config % self.params

        self.configname = configfile[1]
        open(self.configname, 'w').write(configuration)

        # Call parent constructor.
        super(ConfigurationStub, self).__init__()

        # Replace the IO loop.
        self.io_loop = io_loop

        # And then load the config.
        super(ConfigurationStub, self).load_from_file([self.configname])

        # Load paasmaker.yml, if found, and merge in a few select values.
        if os.path.exists('paasmaker.yml'):
          contents = open('paasmaker.yml', 'r').read()
          parsed = yaml.safe_load(contents)

          if 'redis_binary' in parsed:
              self['redis_binary'] = parsed['redis_binary']
          if 'nginx_binary' in parsed:
              self['nginx_binary'] = parsed['nginx_binary']

          self.update_flat()

        # Choose a UUID for ourself.
        #self.set_node_uuid(str(uuid.uuid4()))

        # Change the route that we chose for ourselves, as it seems to
        # be wrong a lot of the time.
        self['my_route'] = '127.0.0.1'
        self.update_flat()

        # And if we're a pacemaker, create the DB.
        if 'pacemaker' in modules:
            self.setup_database()

    def cleanup(self, callback, error_callback):
        """
        Clean up anything set up during this unit tests. This means
        stopping any redis servers that were started, and deleting
        all files and directories that were created.
        """
        # Unsubscribe any listeners, to prevent leaks between tests.
        # This doesn't stop all leaks, but certainly helps.
        pub.unsubAll()

        def finished_shutdown(message):
          # Remove files that we created.
          shutil.rmtree(self.params['scratch_dir'])
          os.unlink(self.configname)
          callback("Completed cleanup.")

        self.shutdown_managed_redis(finished_shutdown, error_callback)

    def get_tornado_configuration(self):
        """
        Overridden tornado settings for unit tests. Forces
        debug mode to be on regardless of any other settings.
        """
        settings = super(ConfigurationStub, self).get_tornado_configuration()
        # Force debug mode on.
        settings['debug'] = True
        return settings

class TestConfigurationStub(unittest.TestCase):
    def test_simple(self):
        stub = ConfigurationStub(modules=['pacemaker', 'heart', 'router'])
        # And I guess we shouldn't have any exceptions...
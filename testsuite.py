#!/usr/bin/env python

import logging
import unittest
import paasmaker
import sys

# Suppress log messages.
# Turning this off temporarily can be helpful for debugging.
#logging.basicConfig(level=logging.DEBUG)
#logging.basicConfig(level=logging.INFO)
#logging.basicConfig(level=logging.ERROR)
logging.basicConfig(level=logging.CRITICAL)

# Define the tests to run. The keys are the modules to search
# in for test cases, and the array is a set of tags that will
# cause this test to be run. To keep the code as generic as possible,
# 'all' is included in each one. 'all' is also the default.
test_sets = {
	paasmaker.util.example: ['all', 'quick', 'example'],
	paasmaker.util.jsonencoder: ['all', 'quick', 'util', 'jsonencoder'],
	paasmaker.util.configurationhelper: ['all', 'quick', 'util', 'configuration'],
	paasmaker.util.joblogging: ['all', 'slow', 'util', 'job'],
	paasmaker.util.port: ['all', 'slow', 'util', 'network'],
	paasmaker.util.plugin: ['all', 'quick', 'util', 'configuration', 'plugin'],
	paasmaker.util.commandsupervisor: ['all', 'slow', 'util', 'process'],
	paasmaker.util.temporaryrabbitmq: ['slow', 'util', 'messaging', 'rabbitmq'],
	paasmaker.util.popen: ['all', 'slow', 'util', 'process'],
	paasmaker.util.streamingchecksum: ['all', 'util', 'checksum'],
	paasmaker.util.processcheck: ['all', 'util', 'process'],
	paasmaker.util.managedrabbitmq: ['slow', 'util', 'messaging', 'managedservice', 'rabbitmq'],
	paasmaker.util.managedredis: ['slow', 'util', 'redis', 'managedservice'],
	paasmaker.util.managedpostgres: ['slow', 'util', 'postgres', 'managedservice'],
	paasmaker.util.managedmysql: ['slow', 'util', 'mysql', 'managedservice'],
	paasmaker.util.asyncdns: ['all', 'slow', 'util', 'network'],

	paasmaker.router.router: ['all', 'slow', 'router'],

	paasmaker.common.configuration.configuration: ['all', 'quick', 'configuration'],
	paasmaker.common.configuration.configurationstub: ['all', 'quick', 'configuration'],
	paasmaker.common.application.configuration: ['all', 'quick', 'configuration'],
	paasmaker.common.core.messageexchange: ['slow', 'messaging', 'exchange', 'job'],
	paasmaker.common.job.manager.backendredis: ['all', 'util', 'job', 'jobmanager', 'slow'],
	paasmaker.common.job.manager.manager: ['util', 'job', 'jobmanager'],

	paasmaker.model: ['all', 'slow', 'model'],

	paasmaker.common.controller.example: ['all', 'quick', 'controller', 'example'],
	paasmaker.common.controller.information: ['all', 'quick', 'controller'],
	paasmaker.common.controller.log: ['all', 'slow', 'controller', 'websocket'],
	paasmaker.pacemaker.controller.user: ['all', 'slow', 'controller', 'user'],
	paasmaker.pacemaker.controller.role: ['all', 'slow', 'controller', 'role'],
	paasmaker.pacemaker.controller.login: ['all', 'slow', 'controller', 'login'],
	paasmaker.pacemaker.controller.node: ['all', 'slow', 'controller', 'node'],
	paasmaker.pacemaker.controller.profile: ['all', 'slow', 'controller', 'profile'],
	paasmaker.pacemaker.controller.workspace: ['all', 'slow', 'controller', 'workspace'],
	paasmaker.pacemaker.controller.upload: ['all', 'controller', 'files'],
	paasmaker.pacemaker.controller.job: ['all', 'slow', 'jobmanager', 'websocket'],
	paasmaker.heart.controller.instance: ['all', 'slow', 'controller', 'instance', 'heart'],

	paasmaker.heart.runtime: ['all', 'slow', 'heart', 'runtime'],
	paasmaker.heart.runtime.php: ['all', 'slow', 'heart', 'runtime', 'php'],
	paasmaker.heart.runtime.shell: ['all', 'slow', 'heart', 'runtime', 'shell'],

	paasmaker.pacemaker.service.parameters: ['all', 'service', 'serviceparameters'],

	paasmaker.pacemaker.prepare.shell: ['all', 'prepare', 'slow', 'shellprepare'],

	paasmaker.pacemaker.scm.zip: ['all', 'scm', 'slow'],
	paasmaker.pacemaker.scm.tarball: ['all', 'scm', 'slow'],

	paasmaker.pacemaker.auth.internal: ['all', 'auth'],
	paasmaker.pacemaker.auth.allowany: ['all', 'auth'],

	paasmaker.common.job.prepare.prepareroot: ['all', 'slow', 'application', 'prepare'],
	paasmaker.common.job.coordinate.selectlocations: ['all', 'slow', 'application', 'coordinate'],
	paasmaker.common.job.coordinate.registerroot: ['all', 'slow', 'application', 'coordinate'],
	paasmaker.common.job.routing.routing: ['all', 'slow', 'application', 'coordinate', 'router'],

	paasmaker.pacemaker.controller.router: ['all', 'slow', 'controller', 'router'],

	paasmaker.pacemaker.placement.default: ['all', 'slow', 'application', 'placement'],

	paasmaker.heart.helper.instancemanager: ['all', 'application', 'heart']
}

if __name__ == '__main__':
	suite = None

	selected = ['all']
	if len(sys.argv) > 1:
		selected = sys.argv[1].split(',')

	print "Selecting unit tests with tags: %s" % str(selected)

	selected = set(selected)
	for module, tags in test_sets.iteritems():
		if len(set(tags).intersection(selected)) > 0:
			if not suite:
				suite = unittest.TestLoader().loadTestsFromModule(module)
			else:
				suite.addTests(unittest.TestLoader().loadTestsFromModule(module))

	if not suite:
		print "No tests selected."
		sys.exit(1)

	# And run them.
	print "About to run %d tests." % suite.countTestCases()
	unittest.TextTestRunner(verbosity=2).run(suite)

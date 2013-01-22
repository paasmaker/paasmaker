#!/usr/bin/env python

import logging
import unittest
import sys
import datetime
from multiprocessing import Pool

import paasmaker

# Suppress log messages.
# Turning this off temporarily can be helpful for debugging.
#logging.basicConfig(level=logging.DEBUG)
#logging.basicConfig(level=logging.INFO)
#logging.basicConfig(level=logging.ERROR)
logging.basicConfig(level=logging.CRITICAL)

# Define the tests to run. The keys are the modules to search
# in for test cases, and the array is a set of tags that will
# cause this test to be run. They should have either 'all' or
# 'slow' as a tag, but not both.
test_sets = {
	paasmaker.util.example: ['all', 'quick', 'example'],
	paasmaker.util.jsonencoder: ['all', 'quick', 'util', 'jsonencoder'],
	paasmaker.util.configurationhelper: ['all', 'quick', 'util', 'configuration'],
	paasmaker.util.joblogging: ['all', 'util', 'job', 'logging'],
	paasmaker.util.port: ['all', 'util', 'network'],
	paasmaker.util.plugin: ['all', 'quick', 'util', 'configuration', 'plugin'],
	paasmaker.util.commandsupervisor: ['all', 'util', 'process'],
	paasmaker.util.temporaryrabbitmq: ['slow', 'util', 'messaging', 'rabbitmq'],
	paasmaker.util.popen: ['all', 'util', 'process'],
	paasmaker.util.streamingchecksum: ['all', 'util', 'checksum'],
	paasmaker.util.processcheck: ['all', 'util', 'process'],
	paasmaker.util.managedrabbitmq: ['slow', 'util', 'messaging', 'managedservice', 'rabbitmq'],
	paasmaker.util.managedredis: ['slow', 'util', 'redis', 'managedservice'],
	paasmaker.util.managedpostgres: ['slow', 'util', 'postgres', 'managedservice'],
	paasmaker.util.managedmysql: ['slow', 'util', 'mysql', 'managedservice'],
	paasmaker.util.managednginx: ['slow', 'util', 'nginx', 'managedservice'],
	paasmaker.util.managedapache: ['slow', 'util', 'apache', 'managedservice'],
	paasmaker.util.asyncdns: ['all', 'util', 'network'],
	paasmaker.util.flattenizr: ['all', 'util', 'data'],

	paasmaker.router.router: ['all', 'router'],
	paasmaker.pacemaker.cron.cronrunner: ['all', 'cron'],

	paasmaker.common.configuration.configuration: ['all', 'configuration'],
	paasmaker.common.configuration.configurationstub: ['all', 'configuration'],
	paasmaker.common.application.configuration: ['all', 'configuration'],
	paasmaker.common.job.manager.backendredis: ['all', 'util', 'job', 'jobmanager', 'jobmanagerbackend'],
	paasmaker.common.job.manager.manager: ['all', 'util', 'job', 'jobmanager', 'jobmanagercore'],

	paasmaker.common.dynamictags.default: ['all', 'dynamictags'],
	paasmaker.common.stats.default: ['all', 'stats'],
	paasmaker.common.score.default: ['all', 'score'],

	paasmaker.model: ['all', 'model'],

	paasmaker.common.controller.example: ['all', 'controller', 'example'],
	paasmaker.common.controller.information: ['all', 'controller'],
	paasmaker.common.controller.log: ['all', 'controller', 'websocket', 'logstream'],
	paasmaker.pacemaker.controller.user: ['all', 'controller', 'user'],
	paasmaker.pacemaker.controller.role: ['all', 'controller', 'role'],
	paasmaker.pacemaker.controller.login: ['all', 'controller', 'login'],
	paasmaker.pacemaker.controller.node: ['all', 'controller', 'node'],
	paasmaker.pacemaker.controller.profile: ['all', 'controller', 'profile'],
	paasmaker.pacemaker.controller.workspace: ['all', 'controller', 'workspace'],
	paasmaker.pacemaker.controller.upload: ['all', 'controller', 'files'],
	paasmaker.pacemaker.controller.job: ['all', 'jobmanager', 'websocket'],
	paasmaker.pacemaker.controller.package: ['all', 'package', 'controller'],
	paasmaker.pacemaker.controller.application: ['all', 'application', 'controller'],
	paasmaker.pacemaker.controller.scmlist: ['all', 'scmlist', 'controller'],
	paasmaker.pacemaker.controller.configuration: ['all', 'configuration', 'controller'],
	paasmaker.heart.controller.instance: ['all', 'controller', 'instance', 'heart'],

	paasmaker.heart.runtime: ['all', 'heart', 'runtime'],
	paasmaker.heart.runtime.php: ['slow', 'heart', 'runtime', 'php'],
	paasmaker.heart.runtime.shell: ['slow', 'heart', 'runtime', 'shell'],
	paasmaker.heart.runtime.rbenv: ['slow', 'heart', 'runtime', 'ruby'],

	paasmaker.heart.unpacker.tarball: ['all', 'heart', 'unpacker'],

	paasmaker.pacemaker.service.parameters: ['all', 'service', 'serviceparameters'],
	paasmaker.pacemaker.service.mysql: ['slow', 'service', 'servicemysql'],
	paasmaker.pacemaker.service.postgres: ['slow', 'service', 'servicepostgres'],
	paasmaker.pacemaker.service.managedredis: ['slow', 'service', 'serviceredis'],
	paasmaker.pacemaker.service.managedpostgres: ['slow', 'service', 'servicemanagedpostgres'],

	paasmaker.pacemaker.packer.tarball: ['all', 'packer', 'tarball'],
	paasmaker.pacemaker.storer.paasmakernode: ['all', 'storer'],

	paasmaker.pacemaker.prepare.shell: ['all', 'prepare', 'shellprepare'],

	paasmaker.pacemaker.scm.zip: ['all', 'scm'],
	paasmaker.pacemaker.scm.tarball: ['all', 'scm'],
	paasmaker.pacemaker.scm.git: ['all', 'scm'],

	paasmaker.pacemaker.scmlist.bitbucket: ['all', 'scmlist', 'slow'],

	paasmaker.pacemaker.auth.internal: ['all', 'auth'],
	paasmaker.pacemaker.auth.allowany: ['all', 'auth'],
	paasmaker.pacemaker.miscplugins.devdatabase: ['all', 'auth'],

	paasmaker.pacemaker.helper.healthmanager: ['all', 'health', 'healthmanager'],
	paasmaker.pacemaker.health.downnodes: ['all', 'health', 'node'],
	paasmaker.pacemaker.health.adjustinstances: ['all', 'health', 'repair'],
	paasmaker.pacemaker.health.stuckjobs: ['all', 'health', 'stuckjobs'],

	paasmaker.common.helper.cleanupmanager: ['all', 'cleanup', 'cleanupmanager'],
	paasmaker.common.cleaner.logs: ['all', 'cleanup'],
	paasmaker.common.cleaner.jobs: ['all', 'cleanup'],

	paasmaker.common.job.prepare.prepareroot: ['all', 'application', 'prepare'],
	paasmaker.common.job.coordinate.selectlocations: ['all', 'application', 'coordinate'],
	paasmaker.common.job.coordinate.register: ['all', 'application', 'coordinate'],
	paasmaker.common.job.routing.routing: ['all', 'application', 'coordinate', 'router'],
	paasmaker.common.job.delete.application: ['all', 'application', 'delete'],

	paasmaker.pacemaker.controller.router: ['all', 'controller', 'router', 'routercontroller'],

	paasmaker.pacemaker.placement.default: ['all', 'application', 'placement'],

	paasmaker.heart.helper.instancemanager: ['all', 'application', 'heart']
}

string_test_sets = {}
for key in test_sets:
	string_test_sets[key.__name__] = key

def run_test(module_name):
	print
	print "------------------------------------------------------------------------"
	print "Testing module", module_name
	suite = unittest.TestLoader().loadTestsFromModule(string_test_sets[module_name])
	result = unittest.TextTestRunner(verbosity=2).run(suite)
	return {
		'failures': len(result.failures),
		'errors': len(result.errors),
		'testsRun': result.testsRun,
		'skipped': len(result.skipped)
	}

if __name__ == '__main__':
	pool = Pool(processes=1, maxtasksperchild=1)

	selected = ['all']
	if len(sys.argv) > 1:
		selected = sys.argv[1].split(',')

	print "Selecting unit tests with tags: %s" % str(selected)

	selected = set(selected)
	modules = []
	for module, tags in test_sets.iteritems():
		if len(set(tags).intersection(selected)) > 0:
			modules.append(module.__name__)

	if len(modules) == 0:
		print "No tests selected."
		sys.exit(2)

	start = datetime.datetime.now()
	try:
		# Wait a max of 120 seconds to complete them.
		results = pool.map_async(run_test, modules).get(120)
	except KeyboardInterrupt:
		pool.terminate()
		print "Cancelled."
		sys.exit(1)

	end = datetime.datetime.now()

	failed = 0
	errors = 0
	run = 0
	skipped = 0

	for result in results:
		failed += result['failures']
		errors += result['errors']
		run += result['testsRun']
		skipped += result['skipped']

	time_taken = (end - start).total_seconds()

	print "Overall, %d run, %d errors, %d failed, %d skipped. Took %0.2fs." % (run, errors, failed, skipped, time_taken)

	if failed > 0:
		sys.exit(1)
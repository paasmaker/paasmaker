#!/usr/bin/env python

import logging
import unittest
import sys
import datetime
import pickle
import tempfile
import subprocess
import os

import coverage
import argparse

# How to invoke the tests:
# * Normal run of a default set of tests:
#   ./testsuite.py
# * A specific tag that matches a set of tests:
#   ./testsuite.py tag
# * Several tags at once:
#   ./testsuite.py tag1,tag2
# * Record coverage, and then show the result of that afterwards:
#   ./testsuite.py -c
#   coverage report -m
# * Change the log level to assist with debugging:
#   ./testsuite.py -l INFO

parser = argparse.ArgumentParser()
parser.add_argument('tags', default="normal", help="A comma seperated list of unit test tags to run.")
parser.add_argument("-c", "--coverage", default=False, help="Compute and store coverage information.", action="store_true")
parser.add_argument("-m", "--module", default=False, help="Run only the given module.", action="store_true")
parser.add_argument("-t", "--temporaryoutput", default=None, help="Temporary output file for a module run.")
parser.add_argument("-l", "--loglevel", default="CRITICAL", help="Log level, one of DEBUG|INFO|WARNING|ERROR|CRITICAL.")

args = parser.parse_args()

# If coverage is turned on, record coverage for "import paasmaker"
# only in the parent test suite - otherwise it uses a lot of CPU time
# and makes the tests take longer.
if args.coverage and not args.module:
	cov = coverage.coverage(source=["paasmaker"], auto_data=True)
	cov.start()

import paasmaker

if args.coverage and not args.module:
	cov.stop()
	cov.save()

# Set the log level.
logging.basicConfig(level=getattr(logging, args.loglevel))

# Define the tests to run. The keys are the modules to search
# in for test cases, and the array is a set of tags that will
# cause this test to be run. They should have either 'normal' or
# 'slow' as a tag, but not both.
test_sets = {
	paasmaker.util.example: ['normal', 'quick', 'example'],
	paasmaker.util.jsonencoder: ['normal', 'quick', 'util', 'jsonencoder'],
	paasmaker.util.configurationhelper: ['normal', 'quick', 'util', 'configuration'],
	paasmaker.util.joblogging: ['normal', 'util', 'job', 'logging'],
	paasmaker.util.port: ['normal', 'util', 'network'],
	paasmaker.util.plugin: ['normal', 'quick', 'util', 'configuration', 'plugin'],
	paasmaker.util.commandsupervisor: ['normal', 'util', 'process'],
	#paasmaker.util.temporaryrabbitmq: ['slow', 'util', 'messaging', 'rabbitmq'],
	paasmaker.util.popen: ['normal', 'util', 'process'],
	paasmaker.util.streamingchecksum: ['normal', 'util', 'checksum'],
	paasmaker.util.processcheck: ['normal', 'util', 'process'],
	#paasmaker.util.managedrabbitmq: ['slow', 'util', 'messaging', 'managedservice', 'rabbitmq'],
	paasmaker.util.redisdaemon: ['util', 'redis', 'managedservice'],
	paasmaker.util.postgresdaemon: ['slow', 'util', 'postgres', 'managedservice'],
	paasmaker.util.mongodaemon: ['util', 'mongodb', 'managedservice'],
	paasmaker.util.mysqldaemon: ['slow', 'util', 'mysql', 'managedservice'],
	paasmaker.util.nginxdaemon: ['slow', 'util', 'nginx', 'managedservice'],
	paasmaker.util.apachedaemon: ['slow', 'util', 'apache', 'managedservice'],
	paasmaker.util.asyncdns: ['normal', 'util', 'network'],
	paasmaker.util.flattenizr: ['normal', 'util', 'data'],

	paasmaker.router.router: ['normal', 'router', 'routeronly'],
	paasmaker.pacemaker.cron.cronrunner: ['normal', 'cron'],

	paasmaker.common.configuration.configuration: ['normal', 'configuration'],
	paasmaker.common.configuration.configurationstub: ['normal', 'configuration'],
	paasmaker.common.application.configuration: ['normal', 'configuration'],
	paasmaker.common.job.manager.backendredis: ['normal', 'util', 'job', 'jobmanager', 'jobmanagerbackend'],
	paasmaker.common.job.manager.manager: ['normal', 'util', 'job', 'jobmanager', 'jobmanagercore'],

	paasmaker.common.dynamictags.default: ['normal', 'dynamictags'],
	paasmaker.common.stats.default: ['normal', 'stats'],
	paasmaker.common.score.default: ['normal', 'score'],

	paasmaker.model: ['normal', 'model'],

	paasmaker.common.controller.example: ['normal', 'controller', 'example'],
	paasmaker.common.controller.information: ['normal', 'controller'],
	paasmaker.common.controller.log: ['normal', 'controller', 'websocket', 'logstream'],
	paasmaker.pacemaker.controller.user: ['normal', 'controller', 'user'],
	paasmaker.pacemaker.controller.role: ['normal', 'controller', 'role'],
	paasmaker.pacemaker.controller.login: ['normal', 'controller', 'login'],
	paasmaker.pacemaker.controller.node: ['normal', 'controller', 'node'],
	paasmaker.pacemaker.controller.profile: ['normal', 'controller', 'profile'],
	paasmaker.pacemaker.controller.workspace: ['normal', 'controller', 'workspace'],
	paasmaker.pacemaker.controller.upload: ['normal', 'controller', 'files'],
	paasmaker.pacemaker.controller.job: ['normal', 'jobmanager', 'websocket', 'jobstream'],
	paasmaker.pacemaker.controller.package: ['normal', 'package', 'controller'],
	paasmaker.pacemaker.controller.application: ['normal', 'application', 'controller'],
	paasmaker.pacemaker.controller.scmlist: ['normal', 'scmlist', 'controller'],
	paasmaker.pacemaker.controller.configuration: ['normal', 'configuration', 'controller'],
	paasmaker.heart.controller.instance: ['normal', 'controller', 'instance', 'heart'],

	paasmaker.heart.runtime: ['normal', 'heart', 'runtime'],
	paasmaker.heart.runtime.php: ['slow', 'heart', 'runtime', 'php'],
	paasmaker.heart.runtime.shell: ['slow', 'heart', 'runtime', 'shell'],
	paasmaker.heart.runtime.rbenv: ['slow', 'heart', 'runtime', 'ruby'],

	paasmaker.heart.unpacker.tarball: ['normal', 'heart', 'unpacker'],
	paasmaker.heart.startup.filesystemlinker: ['normal', 'heart', 'filesystem'],

	paasmaker.pacemaker.service.parameters: ['normal', 'service', 'serviceparameters'],
	paasmaker.pacemaker.service.filesystem: ['normal', 'service', 'filesystem'],
	paasmaker.pacemaker.service.mysql: ['slow', 'service', 'servicemysql', 'mysql'],
	paasmaker.pacemaker.service.postgres: ['slow', 'service', 'servicepostgres', 'postgres'],
	paasmaker.pacemaker.service.managedredis: ['service', 'serviceredis', 'redis'],
	paasmaker.pacemaker.service.managedmongodb: ['service', 'mongodb'],
	paasmaker.pacemaker.service.managedpostgres: ['slow', 'service', 'servicemanagedpostgres', 'postgres'],
	paasmaker.pacemaker.service.managedmysql: ['slow', 'service', 'servicemanagedmysql', 'mysql'],

	paasmaker.pacemaker.packer.tarball: ['normal', 'packer', 'tarball'],
	paasmaker.pacemaker.storer.paasmakernode: ['all', 'storer'],

	paasmaker.pacemaker.prepare.shell: ['normal', 'prepare', 'shellprepare'],

	paasmaker.pacemaker.scm.zip: ['normal', 'scm'],
	paasmaker.pacemaker.scm.tarball: ['normal', 'scm'],
	paasmaker.pacemaker.scm.git: ['normal', 'scm'],

	paasmaker.pacemaker.scmlist.bitbucket: ['normal', 'scmlist', 'slow'],

	paasmaker.pacemaker.auth.internal: ['normal', 'auth'],
	paasmaker.pacemaker.auth.allowany: ['normal', 'auth'],
	paasmaker.pacemaker.miscplugins.devdatabase: ['normal', 'auth'],

	paasmaker.pacemaker.helper.healthmanager: ['normal', 'health', 'healthmanager'],
	paasmaker.pacemaker.health.downnodes: ['normal', 'health', 'node'],
	paasmaker.pacemaker.health.adjustinstances: ['normal', 'health', 'repair'],
	paasmaker.pacemaker.health.stuckjobs: ['normal', 'health', 'stuckjobs'],

	paasmaker.common.helper.cleanupmanager: ['all', 'cleanup', 'cleanupmanager'],
	paasmaker.common.cleaner.logs: ['normal', 'cleanup'],
	paasmaker.common.cleaner.jobs: ['normal', 'cleanup'],

	paasmaker.common.job.prepare.prepareroot: ['normal', 'application', 'prepare'],
	paasmaker.common.job.coordinate.selectlocations: ['normal', 'application', 'coordinate'],
	paasmaker.common.job.coordinate.register: ['normal', 'application', 'coordinate'],
	paasmaker.common.job.routing.routing: ['normal', 'application', 'coordinate', 'router'],
	paasmaker.common.job.delete.application: ['normal', 'application', 'delete'],

	paasmaker.pacemaker.controller.router: ['normal', 'controller', 'router', 'routercontroller'],

	paasmaker.pacemaker.placement.default: ['normal', 'application', 'placement'],

	paasmaker.heart.helper.instancemanager: ['normal', 'application', 'heart']
}

string_test_sets = {}
for key in test_sets:
	string_test_sets[key.__name__] = key

def run_test(module_name):
	print
	print "------------------------------------------------------------------------"
	print "Testing module", module_name

	if args.coverage:
		cov = coverage.coverage(source=["paasmaker"], auto_data=True)
		cov.start()

	suite = unittest.TestLoader().loadTestsFromModule(string_test_sets[module_name])
	result = unittest.TextTestRunner(verbosity=2).run(suite)

	if args.coverage:
		cov.stop()
		cov.save()

	return {
		'failures': len(result.failures),
		'errors': len(result.errors),
		'testsRun': result.testsRun,
		'skipped': len(result.skipped)
	}

if __name__ == '__main__':
	# See if we're in the subprocess-run-only-one module mode.
	if args.module:
		module_name = args.tags

		result = run_test(module_name)

		if args.temporaryoutput:
			output = open(args.temporaryoutput, 'wb')
			pickle.dump(result, output)

		sys.exit(0)

	# Otherwise, choose the tests to run.
	selected = args.tags.split(',')

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
	failed = 0
	errors = 0
	run = 0
	skipped = 0
	try:
		for module in modules:
			temporary_name = tempfile.mkstemp()[1]
			arguments = [sys.argv[0], module, '-m', '-t', temporary_name]
			if args.coverage:
				arguments.append("-c")
			arguments.extend(['-l', args.loglevel])

			subprocess.check_call(arguments)

			input_file = open(temporary_name, 'rb')
			results = pickle.load(input_file)

			failed += results['failures']
			errors += results['errors']
			run += results['testsRun']
			skipped += results['skipped']

			input_file.close()
			os.unlink(temporary_name)

	except KeyboardInterrupt:
		print "Cancelled."
		sys.exit(1)

	end = datetime.datetime.now()

	time_taken = (end - start).total_seconds()

	print "Overall, %d run, %d errors, %d failed, %d skipped. Took %0.2fs." % (run, errors, failed, skipped, time_taken)

	if failed > 0 or errors > 0:
		sys.exit(1)

	# Once the tests are completed, use "coverage report -m" to
	# show the coverage.
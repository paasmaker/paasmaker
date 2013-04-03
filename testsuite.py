#!/usr/bin/env python

#
# Paasmaker - Platform as a Service
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#

import logging
import unittest
import sys
import datetime
import math
import pickle
import tempfile
import subprocess
import os

# Check that the virtualenv exists.
if not os.path.exists("thirdparty/python/bin/pip"):
	print "virtualenv not installed. Run install.py to set up this directory properly."
	sys.exit(1)

# Activate the environment now, inside this script.
bootstrap_script = "thirdparty/python/bin/activate_this.py"
execfile(bootstrap_script, dict(__file__=bootstrap_script))

import paasmaker
import paasmaker.integration

import coverage
import argparse

########################################
# Examples of running this file
#
# * Show help and exit:
#   ./testsuite.py
# * A specific tag that matches a set of tests:
#   ./testsuite.py heart
# * Several tags at once:
#   ./testsuite.py util runtime
# * Record coverage, and then show the result of that afterwards:
#   ./testsuite.py -c all
#   coverage report -m
# * Change the log level to assist with debugging:
#   ./testsuite.py -l INFO normal
########################################

# Define the tests to run. The keys are the modules to search
# in for test cases, and the array is a set of tags that will
# cause this test to be run. All items should have either
# 'normal' or 'slow' as a tag, but not both.
test_sets = {
	paasmaker.util.example: ['normal', 'quick', 'example'],
	paasmaker.util.jsonencoder: ['normal', 'quick', 'util', 'jsonencoder'],
	paasmaker.util.configurationhelper: ['normal', 'quick', 'util', 'configuration'],
	paasmaker.util.joblogging: ['normal', 'util', 'job', 'logging'],
	paasmaker.util.port: ['normal', 'util', 'network'],
	paasmaker.util.plugin: ['normal', 'quick', 'util', 'configuration', 'plugin'],
	paasmaker.util.commandsupervisor: ['normal', 'util', 'process', 'supervisor'],
	#paasmaker.util.temporaryrabbitmq: ['slow', 'util', 'messaging', 'rabbitmq'],
	paasmaker.util.popen: ['normal', 'util', 'process'],
	paasmaker.util.streamingchecksum: ['normal', 'util', 'checksum'],
	paasmaker.util.processcheck: ['normal', 'util', 'process'],
	#paasmaker.util.managedrabbitmq: ['slow', 'util', 'messaging', 'managedservice', 'rabbitmq'],
	paasmaker.util.redisdaemon: ['util', 'redis', 'managedservice'],
	paasmaker.util.postgresdaemon: ['slow', 'util', 'postgres', 'managedservice', 'postgresdaemon'],
	paasmaker.util.mongodaemon: ['util', 'mongodb', 'managedservice', 'mongodaemon'],
	paasmaker.util.mysqldaemon: ['slow', 'util', 'mysql', 'managedservice', 'mysqldaemon'],
	paasmaker.util.nginxdaemon: ['slow', 'util', 'nginx', 'managedservice', 'nginxdaemon'],
	paasmaker.util.apachedaemon: ['slow', 'util', 'apache', 'managedservice', 'apachedaemon'],
	paasmaker.util.asyncdns: ['normal', 'util', 'network'],
	paasmaker.util.flattenizr: ['normal', 'util', 'data'],
	paasmaker.util.threadcallback: ['normal', 'util', 'thread'],

	paasmaker.router.router: ['normal', 'router', 'routeronly'],
	paasmaker.pacemaker.cron.cronrunner: ['normal', 'cron'],

	paasmaker.common.configuration.configuration: ['normal', 'configuration'],
	paasmaker.common.configuration.configurationstub: ['normal', 'configuration'],
	paasmaker.common.application.configuration: ['normal', 'configuration'],
	paasmaker.common.job.manager.backendredis: ['normal', 'util', 'job', 'jobmanager', 'jobmanagerbackend'],
	paasmaker.common.job.manager.manager: ['normal', 'util', 'job', 'jobmanager', 'jobmanagercore'],

	paasmaker.common.dynamictags.default: ['normal', 'dynamictags'],
	paasmaker.common.dynamictags.ec2: ['normal', 'dynamictags'],
	paasmaker.common.stats.default: ['normal', 'stats'],
	paasmaker.common.score.default: ['normal', 'score'],

	paasmaker.model: ['normal', 'model'],

	paasmaker.common.controller.example: ['normal', 'controller', 'example'],
	paasmaker.common.controller.information: ['normal', 'controller'],
	paasmaker.pacemaker.controller.user: ['normal', 'controller', 'user'],
	paasmaker.pacemaker.controller.role: ['normal', 'controller', 'role'],
	paasmaker.pacemaker.controller.login: ['normal', 'controller', 'login'],
	paasmaker.pacemaker.controller.node: ['normal', 'controller', 'node'],
	paasmaker.pacemaker.controller.profile: ['normal', 'controller', 'profile'],
	paasmaker.pacemaker.controller.workspace: ['normal', 'controller', 'workspace'],
	paasmaker.pacemaker.controller.upload: ['normal', 'controller', 'files', 'upload'],
	paasmaker.pacemaker.controller.job: ['normal', 'jobmanager', 'websocket', 'jobstream'],
	paasmaker.pacemaker.controller.package: ['normal', 'package', 'controller'],
	paasmaker.pacemaker.controller.application: ['normal', 'application', 'controller'],
	paasmaker.pacemaker.controller.scmlist: ['normal', 'scmlist', 'controller'],
	paasmaker.pacemaker.controller.configuration: ['normal', 'configuration', 'controller'],
	paasmaker.pacemaker.controller.stream: ['normal', 'stream', 'controller'],
	paasmaker.heart.controller.instance: ['normal', 'controller', 'instance', 'heart'],

	paasmaker.heart.runtime: ['normal', 'heart', 'runtime'],
	paasmaker.heart.runtime.php: ['slow', 'heart', 'runtime', 'php'],
	paasmaker.heart.runtime.static: ['slow', 'heart', 'runtime', 'static'],
	paasmaker.heart.runtime.shell: ['slow', 'heart', 'runtime', 'shell'],
	paasmaker.heart.runtime.rbenv: ['slow', 'heart', 'runtime', 'ruby'],
	paasmaker.heart.runtime.nvm: ['slow', 'heart', 'runtime', 'nodejs'],

	paasmaker.heart.unpacker.tarball: ['normal', 'heart', 'unpacker'],
	paasmaker.heart.startup.filesystemlinker: ['normal', 'heart', 'filesystem'],

	paasmaker.pacemaker.service.parameters: ['normal', 'service', 'serviceparameters'],
	paasmaker.pacemaker.service.filesystem: ['normal', 'service', 'filesystem'],
	paasmaker.pacemaker.service.s3bucket: ['normal', 'service', 's3', 'amazonaws'],
	paasmaker.pacemaker.service.mysql: ['slow', 'service', 'servicemysql', 'mysql'],
	paasmaker.pacemaker.service.postgres: ['slow', 'service', 'servicepostgres', 'postgres'],
	paasmaker.pacemaker.service.managedredis: ['service', 'serviceredis', 'redis'],
	paasmaker.pacemaker.service.managedmongodb: ['service', 'mongodb'],
	paasmaker.pacemaker.service.managedpostgres: ['slow', 'service', 'servicemanagedpostgres', 'postgres'],
	paasmaker.pacemaker.service.managedmysql: ['slow', 'service', 'servicemanagedmysql', 'mysql'],

	paasmaker.pacemaker.packer.tarball: ['normal', 'packer', 'tarball'],
	paasmaker.pacemaker.storer.paasmakernode: ['normal', 'storer'],

	paasmaker.pacemaker.prepare.shell: ['normal', 'prepare', 'shellprepare'],
	paasmaker.pacemaker.prepare.pythonpip: ['normal', 'prepare', 'pipprepare'],

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
	paasmaker.pacemaker.health.routerdowninstances: ['normal', 'health', 'repair', 'routerrepair'],

	paasmaker.common.helper.periodicmanager: ['normal', 'periodic', 'periodicmanager'],
	paasmaker.common.periodic.logs: ['normal', 'periodic'],
	paasmaker.common.periodic.jobs: ['normal', 'periodic'],

	paasmaker.common.job.prepare.prepareroot: ['normal', 'application', 'prepare'],
	paasmaker.common.job.coordinate.selectlocations: ['normal', 'application', 'coordinate'],
	paasmaker.common.job.coordinate.register: ['normal', 'application', 'coordinate'],
	paasmaker.common.job.routing.routing: ['normal', 'application', 'coordinate', 'router'],
	paasmaker.common.job.delete.application: ['normal', 'application', 'delete'],

	paasmaker.pacemaker.controller.router: ['normal', 'controller', 'router', 'routercontroller'],

	paasmaker.pacemaker.placement.default: ['normal', 'application', 'placement'],

	paasmaker.heart.helper.instancemanager: ['normal', 'application', 'heart', 'instancemanager'],

	paasmaker.integration.example: ['integration', 'i-example'],
	paasmaker.integration.workspace: ['integration', 'i-workspace'],
	paasmaker.integration.user: ['integration', 'i-user']
}

########################################

def tags_with_count():
	all_tags = {}
	for module, tags in test_sets.iteritems():
		for tag in tags:
			if tag in all_tags:
				all_tags[tag] += 1
			else:
				all_tags[tag] = 1
	return all_tags

def tag_help():
	all_tags = tags_with_count()
	sorted_tags = sorted(all_tags.keys())

	retval = "available tags:\n"

	# do some deuglified formatting
	tty_rows, tty_columns = os.popen('stty size', 'r').read().split()
	column_width = max(len(tag) for tag in sorted_tags) + 13
	columns_per_row = math.floor(int(tty_columns) / column_width)

	for index, tag in enumerate(sorted_tags):
		if all_tags[tag] == 1:
			retval += ("  %s (1 test)" % tag).ljust(column_width)
		else:
			retval += ("  %s (%d tests)" % (tag, all_tags[tag])).ljust(column_width)
		if index % columns_per_row == (columns_per_row - 1):
			retval += "\n"

	return retval

string_test_sets = {}
for key in test_sets:
	string_test_sets[key.__name__] = key

########################################

parser = argparse.ArgumentParser(epilog=tag_help(), formatter_class=argparse.RawDescriptionHelpFormatter)
parser.add_argument('test_tags', help="list of unit test tags to run (separated by commas or spaces), or \"all\"", nargs=argparse.REMAINDER)
parser.add_argument("-c", "--coverage", default=False, help="measure code coverage while running tests; data is saved into .coverage.* files, and can be displayed with `coverage report -m`", action="store_true")
parser.add_argument("-m", "--module", default=False, help="only run tests for the given module")
parser.add_argument("-t", "--temporaryoutput", default=None, help="temporary output file for a module run", metavar="FILE")
parser.add_argument("-l", "--loglevel", default="CRITICAL", help="log output verbosity level", choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])

if len(sys.argv) == 1:
	# hackish override for argparse.error()
	parser.print_help(sys.stderr)
	sys.exit(1)

args = parser.parse_args()

if args.coverage:
	print "Code coverage enabled: clearing previous coverage data"
	subprocess.check_call(['coverage', 'erase'])

# Set the log level.
logging.basicConfig(level=getattr(logging, args.loglevel))

########################################

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

########################################

if __name__ == '__main__':
	# See if we're in the subprocess-run-only-one module mode.
	if args.module:
		result = run_test(args.module)

		if args.temporaryoutput:
			output = open(args.temporaryoutput, 'wb')
			pickle.dump(result, output)

		sys.exit(0)

	# Otherwise, choose the tests to run.
	selected = []
	for item in args.test_tags:
		selected.extend(item.split(','))
	if selected[0] == 'all':
		selected = tags_with_count().keys()

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

			if args.coverage:
				arguments = [
					'coverage', 'run',
					'-p',
					'--omit=*.generated.py,thirdparty/*',
					'--source', os.path.dirname(os.path.realpath(__file__)),
					sys.argv[0], '-m', module, '-t', temporary_name,
					'-l', args.loglevel
				]
			else:
				arguments = [sys.argv[0], '-m', module, '-t', temporary_name, '-l', args.loglevel]

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

	if args.coverage and not args.module:
		subprocess.check_call(['coverage', 'combine'])
		print "Run `coverage report -m` to see coverage results"

	if failed > 0 or errors > 0:
		sys.exit(1)

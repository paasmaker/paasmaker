#!/usr/bin/env python

import logging
import unittest
import paasmaker
import sys

# Suppress log messages.
# Turning this off temporarily can be helpful for debugging.
#logging.basicConfig(level=logging.DEBUG)
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
	paasmaker.util.plugin: ['all', 'quick', 'util', 'configuration'],
	paasmaker.util.commandsupervisor: ['all', 'slow', 'util', 'process'],
	paasmaker.util.memoryrabbitmq: ['all', 'slow', 'util', 'messaging', 'service'],
	paasmaker.util.popen: ['all', 'slow', 'util', 'process'],

	paasmaker.configuration.configuration: ['all', 'quick', 'configuration'],
	paasmaker.application.configuration: ['all', 'quick', 'configuration'],

	paasmaker.model: ['all', 'slow', 'model'],

	paasmaker.controller.example: ['all', 'quick', 'controller'],
	paasmaker.controller.information: ['all', 'quick', 'controller'],
	paasmaker.controller.log: ['all', 'slow', 'controller'],
	paasmaker.controller.login: ['all', 'slow', 'controller'],

	paasmaker.heart.runtime: ['all', 'slow', 'heart', 'runtime'],
	paasmaker.heart.runtime.php: ['all', 'slow', 'heart', 'runtime', 'php']
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

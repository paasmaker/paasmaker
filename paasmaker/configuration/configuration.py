#!/usr/bin/env python

import paasmaker
import collections
import unittest
import os
import logging
import warnings

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

class Configuration:
	def __init__(self):
		self.values = self.defaults()

	def load(self, configuration_file = None):
		loader = paasmaker.configuration.Loader()
		raw = loader.load(configuration_file)
		if raw:
			update(self.values, raw)
		else:
			logger.warning("Unable to parse configuration, or configuration empty - loading '%s'", loader.get_loaded_filename())			

	def defaults(self):
		defaults = {}

		defaults['global'] = {}
		defaults['global']['http_port'] = 8888
		defaults['global']['my_route'] = None

		defaults['pacemaker'] = {}
		defaults['pacemaker']['dsn'] = 'sqlite3:///tmp/paasmaker.db'

		return defaults

	def dump(self):
		logger.debug("Configuration: %s", str(self.values))

	def get_raw(self):
		# TODO: This feels too... raw...
		return self.values

# From: http://stackoverflow.com/questions/3232943/update-value-of-a-nested-dictionary-of-varying-depth
# Thanks, this is epic win!
def update(d, u):
	for k, v in u.iteritems():
		if isinstance(v, collections.Mapping):
			r = update(d.get(k, {}), v)
			d[k] = r
		else:
			d[k] = u[k]

	return d

class TestConfiguration(unittest.TestCase):
	def setUp(self):
		# Ignore the warning when using tmpnam. tmpnam is fine for the test.
		warnings.simplefilter("ignore")

		self.tempnam = os.tempnam()

	def tearDown(self):
		if os.path.exists(self.tempnam):
			os.unlink(self.tempnam)

	def test_fail_load(self):
		config = Configuration()
		self.assertRaises(IOError, config.load, 'test_failure.yml')

		open(self.tempnam, 'w').write("test:\n  foo: 10")
		config = Configuration()
		config.load(self.tempnam)
		self.assertEquals(config.get_raw()['test']['foo'], 10)

	def test_simple_default(self):
		open(self.tempnam, 'w').write("")
		config = Configuration()
		config.load(self.tempnam)
		self.assertEqual(config.get_raw()['global']['http_port'], 8888, 'No default present.')

if __name__ == '__main__':
	unittest.main()

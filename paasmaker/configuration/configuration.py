#!/usr/bin/env python

import paasmaker
import collections

class Configuration:
	def __init__(self, configuration_file_override = None):
		self.defaults()
		loader = paasmaker.configuration.Loader()
		raw = loader.load(configuration_file_override)
		update(self.values, raw)

	def defaults(self):
		defaults = {}

		defaults['global'] = {}
		defaults['global']['http_port'] = 8888
		defaults['global']['my_route'] = None

		defaults['pacemaker'] = {}
		defaults['pacemaker']['dsn'] = 'sqlite3:///tmp/paasmaker.db'

		self.values = defaults

	def dump(self):
		print str(self.values)

	def get_raw(self):
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

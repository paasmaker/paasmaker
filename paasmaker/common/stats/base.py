#
# Paasmaker - Platform as a Service
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#

import paasmaker

import tornado.testing
import colander

class BaseStatsConfigurationSchema(colander.MappingSchema):
	# No options defined.
	pass

class BaseStats(paasmaker.util.plugin.Plugin):
	"""
	This plugin is used to fetch stats on the node, which are
	reported back to the master for informational purposes.
	Additionally, these stats are used by scoring plugins to
	calculate the "score" for a node. The score is used by
	the Pacemaker to rank nodes when determining where to place
	applications.

	These plugins are called each time the node reports back
	to the master node.
	"""
	MODES = {
		paasmaker.util.plugin.MODE.NODE_STATS: None
	}
	OPTIONS_SCHEMA = BaseStatsConfigurationSchema()

	def stats(self, existing_stats, callback):
		"""
		Alter or insert into the provided existing stats array. Call the callback
		with the dictionary once completed.

		For example::

			def stats(self, existing_stats, callback):
				existing_stats['my_stat'] = 1.0
				callback(existing_stats)

		:arg dict existing_stats: The existing stats. Insert your stats into
			this dictionary.
		:arg callable callback: The callback to call once done.
		"""
		raise NotImplementedError("You must implement stats().")

class BaseStatsTest(tornado.testing.AsyncTestCase):
	def setUp(self):
		super(BaseStatsTest, self).setUp()
		self.configuration = paasmaker.common.configuration.ConfigurationStub(0, ['pacemaker'], io_loop=self.io_loop)

	def tearDown(self):
		self.configuration.cleanup(self.stop, self.stop)
		self.wait()
		super(BaseStatsTest, self).tearDown()
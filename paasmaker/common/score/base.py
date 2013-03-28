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

class BaseScoreConfigurationSchema(colander.MappingSchema):
	# No options defined.
	pass

class BaseScore(paasmaker.util.plugin.Plugin):
	"""
	Score plugins are used to take a set of stats for a node,
	and return a number that can be used to rank nodes when
	placing applications.

	These plugins are called each time a node reports back to
	the master node.
	"""

	MODES = {
		paasmaker.util.plugin.MODE.NODE_SCORE: None
	}
	OPTIONS_SCHEMA = BaseScoreConfigurationSchema()

	def score(self, stats):
		"""
		From the given stats dict, calculate a score for the node.
		It should be between 0 and 1 (fractional), but you can return
		values bigger than 1 to really emphasise that the node is overloaded.

		You should test values in stats to see if they exist,
		and not assume that they do.

		The score value is returned. This is called sychronously
		each time the node registers with the master, so you
		won't want to spend a long time.
		"""
		raise NotImplementedError("You must implement score().")

class BaseScoreTest(tornado.testing.AsyncTestCase):
	def setUp(self):
		super(BaseScoreTest, self).setUp()
		self.configuration = paasmaker.common.configuration.ConfigurationStub(0, ['pacemaker'], io_loop=self.io_loop)

	def tearDown(self):
		self.configuration.cleanup()
		super(BaseScoreTest, self).tearDown()
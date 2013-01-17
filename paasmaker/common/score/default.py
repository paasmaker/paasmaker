
import json

import paasmaker

from base import BaseScore, BaseScoreTest

class DefaultScore(BaseScore):
	def score(self, stats):
		# TODO: Do different things based on the platform for the stats.
		# TODO: Evaluate if this algorithm chooses good results or not.

		# This algorithm calculates a few scores for various
		# metrics, and then chooses the highest as the score
		# for this node.

		# A score for the disk used.
		disk_score = float(stats['disk_free']) / float(stats['disk_total'])
		self.logger.debug("Disk space score: %0.2f (%d/%d)", disk_score, stats['disk_free'], stats['disk_total'])

		# A score for the overall load.
		load_score = float(stats['load']) / float(stats['cpus'])
		self.logger.debug("Load score: %0.2f (%0.2f/%d)", load_score, stats['load'], stats['cpus'])

		# A score for memory free.
		# For this one, ignore buffers and cache.
		memory_score = float(stats['memory']['adjusted_free']) / float(stats['memory']['total'])
		self.logger.debug("Memory score: %0.2f (%d/%d)", memory_score, stats['memory']['adjusted_free'], stats['memory']['total'])

		# A score for swap used. If it's greater than 25%, automatically insert
		# a score of 2.0 - because we'll want to stop using this node.
		# TODO: This will probably bite someone in production.
		swap_score = float(stats['memory']['swap_used']) / float(stats['memory']['swap_total'])
		self.logger.debug("Swap score: %0.4f (%d/%d)", swap_score, stats['memory']['swap_used'], stats['memory']['swap_total'])
		if swap_score > 0.25:
			self.logger.info("Swap usage is above 25%, adjusting score so as to not use this node.")
			swap_score = 2.0

		# Now find the highest score.
		highest_score = max(disk_score, load_score, memory_score, swap_score)
		self.logger.debug("Overall node score: %0.2f", highest_score)

		return highest_score

class DefaultScoreTest(BaseScoreTest):
	def setUp(self):
		super(DefaultScoreTest, self).setUp()

		self.configuration.plugins.register(
			'paasmaker.stats.default',
			'paasmaker.common.stats.default.DefaultStats',
			{},
			'Default Node Stats generator'
		)

		self.configuration.plugins.register(
			'paasmaker.score.default',
			'paasmaker.common.score.default.DefaultScore',
			{},
			'Default Node Score assessor'
		)

	def test_simple(self):
		stats_plugin = self.configuration.plugins.instantiate(
			'paasmaker.stats.default',
			paasmaker.util.plugin.MODE.NODE_STATS
		)

		stats = {}
		stats_plugin.stats(stats)

		#print json.dumps(stats, indent=4, sort_keys=True)

		plugin = self.configuration.plugins.instantiate(
			'paasmaker.score.default',
			paasmaker.util.plugin.MODE.NODE_SCORE
		)

		score = plugin.score(stats)

		self.assertTrue(score > 0, "Score should not be zero.")
		# TODO: The score can be more than 1, so this unit test
		# will become a hiesen test.
		self.assertTrue(score < 1.0, "Score should be less than one.")

import json
import math

import paasmaker

from base import BaseScore, BaseScoreTest

class DefaultScore(BaseScore):
	def score(self, stats):
		# TODO: Do different things based on the platform for the stats.
		# TODO: Evaluate if this algorithm chooses good results or not.

		# This algorithm calculates a score for each of a few health metrics, on
		# a scale of 0 to 1 (although values greater than 1 are possible).
		# Lower is better, and 0% usage should give a score of 0.
		# The highest / worst of the individual scores is
		# returned as being representative of the node.

		# A score for the disk used: linear from 0 (disk is entirely free) to 1 (no free space)
		disk_score = 1 - float(stats['disk_free']) / float(stats['disk_total'])
		self.logger.debug("Disk space score: %0.2f (%d/%d)", disk_score, stats['disk_free'], stats['disk_total'])

		# A score for the overall load: just divide load average by number of
		# cores, since load average is already on a 0 (quiet) to 1 (busy) scale
		load_score = float(stats['load']) / float(stats['cpus'])
		self.logger.debug("Load score: %0.2f (%0.2f/%d)", load_score, stats['load'], stats['cpus'])

		# Memory score: linear from 0 (all memory is unused) to 1 (no unused memory)
		# mem_adjusted_free counts buffers and cache as free memory
		memory_score = 1 - float(stats['mem_adjusted_free']) / float(stats['mem_total'])
		self.logger.debug("Memory score: %0.2f (%d/%d)", memory_score, stats['mem_adjusted_free'], stats['mem_total'])

		# A score for swap used: e^(32*swap_ratio-8)
		# where swap ratio is swap_used as a fraction of total physical memory
		# 0    when swap is 0% used
		# 0.25 when swap is 20.67% used
		# 1.0  when swap is 25% used
		# 2.0  when swap is 27.17% used
		swap_score = math.exp(32 * (float(stats['swap_used']) / float(stats['mem_total'])) - 8)
		self.logger.debug("Swap score: %0.4f (%d/%d)", swap_score, stats['swap_used'], stats['mem_total'])

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
		self.assertTrue(score > 0, "Score should be non-zero.")
		self.assertTrue(float(score) == score, "Score is not a float.")

	def test_score_computation(self):
		stats_plugin = self.configuration.plugins.instantiate(
			'paasmaker.stats.default',
			paasmaker.util.plugin.MODE.NODE_STATS
		)

		plugin = self.configuration.plugins.instantiate(
			'paasmaker.score.default',
			paasmaker.util.plugin.MODE.NODE_SCORE
		)

		score = plugin.score({
			"cpus": 1,
			"load": 0,
			"swap_used": 0,
			"mem_adjusted_free": 4,
			"mem_total": 4,
			"disk_total": 10,
			"disk_free": 10
		})
		# use round here because the highest score in this case is math.exp(-8) = 0.0003
		self.assertTrue(round(score, 3) == 0, ("Score when everything is free should equal 0.000 (got %0.2f)." % score))

		score = plugin.score({
			"cpus": 1,
			"load": 0,
			"swap_used": 0,
			"mem_adjusted_free": 4,
			"mem_total": 4,
			"disk_total": 10,
			"disk_free": 1
		})
		self.assertTrue(score == 0.9, ("Score when disk is 10%% free should equal 0.9 (got %0.2f)." % score))

		score = plugin.score({
			"cpus": 2,
			"load": 1,
			"swap_used": 0,
			"mem_adjusted_free": 4,
			"mem_total": 4,
			"disk_total": 10,
			"disk_free": 10
		})
		self.assertTrue(score == 0.5, ("Score when load average is 1.0 on two CPUs should equal 0.5 (got %0.2f)." % score))

		score = plugin.score({
			"cpus": 1,
			"load": 0,
			"swap_used": 0,
			"mem_adjusted_free": 1,
			"mem_total": 4,
			"disk_total": 10,
			"disk_free": 10
		})
		self.assertTrue(score == 0.75, ("Score when memory is 25%% free should equal 0.75 (got %0.2f)." % score))

		score = plugin.score({
			"cpus": 1,
			"load": 0,
			"swap_used": 1,
			"mem_adjusted_free": 4,
			"mem_total": 4,
			"disk_total": 10,
			"disk_free": 10
		})
		self.assertTrue(score == 1, ("Score when swap space equals 25%% of real memory should equal 1 (got %0.2f)." % score))

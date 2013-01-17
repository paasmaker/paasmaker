
import os
import platform
import ctypes
import json

import paasmaker
from base import BaseStats, BaseStatsTest

import tornado.process

# These two functions are a mix of two things:
# http://stackoverflow.com/questions/51658/cross-platform-space-remaining-on-volume-using-python
# http://atlee.ca/blog/2008/02/23/getting-free-diskspace-in-python/
def get_free_space(path):
	"""
	Return folder/drive free space (in bytes)
	"""
	if platform.system() == 'Windows':
		free_bytes = ctypes.c_ulonglong(0)
		ctypes.windll.kernel32.GetDiskFreeSpaceExW(ctypes.c_wchar_p(path), None, None, ctypes.pointer(free_bytes))
		return free_bytes.value
	else:
		s = os.statvfs(path)
		return s.f_bsize * s.f_bavail

def get_total_space(path):
	"""
	Return folder/drive total space (in bytes)
	"""
	if platform.system() == 'Windows':
		total_bytes = ctypes.c_ulonglong(0)
		ctypes.windll.kernel32.GetDiskFreeSpaceExW(ctypes.c_wchar_p(path), None, ctypes.pointer(total_bytes), None)
		return total_bytes.value
	else:
		s = os.statvfs(path)
		return s.f_bsize * s.f_blocks

class DefaultStats(BaseStats):
	def stats(self, existing_stats):
		# TODO: Make this work on other platforms.

		# Include the platform - this allows score plugins to make
		# more informed decisions.
		existing_stats['platform'] = platform.system()

		# Calculate memory.
		existing_stats['memory'] = self._linux_memory()

		# Calculate the total bytes free. This ends up using figures
		# from the disk that has the highest percent used. TODO: Figure out
		# if this is a good idea.
		# To make it accurate, it checks the folders configured as scratch,
		# logs, and heart.
		paths = [
			self.configuration.get_flat('scratch_directory'),
			self.configuration.get_flat('log_directory')
		]
		if self.configuration.is_heart():
			paths.append(self.configuration.get_flat('heart.working_dir'))

		free = None
		total = None
		highest_usage = None
		for path in paths:
			this_free = get_free_space(path)
			this_total = get_total_space(path)

			if highest_usage is None:
				free = this_free
				total = this_total
				highest_usage = float(free) / float(total)
			else:
				this_usage = float(free) / float(total)
				if this_usage > highest_usage:
					free = this_free
					total = this_total
					highest_usage = this_usage

		existing_stats['disk_free'] = free
		existing_stats['disk_total'] = total

		# TODO: CPU usage. This requires it to be async, as we need
		# to wait to collect this data.

		existing_stats.update(self._linux_loadavg())

	def _linux_memory(self):
		# TODO: This is very crude. Fix it.
		result = {}
		raw_memory = open('/proc/meminfo', 'r').readlines()

		def extract(ln):
			bits = ln.split(":")
			figure = bits[1].strip()
			bits = figure.split(' ')
			figure = int(bits[0])
			if bits[1] == 'kB':
				figure *= 1024
			return figure

		for line in raw_memory:
			if line.startswith("MemTotal:"):
				result['total'] = extract(line)
			if line.startswith("MemFree:"):
				result['free'] = extract(line)
			if line.startswith("Buffers:"):
				result['buffers'] = extract(line)
			if line.startswith("Cached:"):
				result['cached'] = extract(line)
			if line.startswith("SwapTotal:"):
				result['swap_total'] = extract(line)
			if line.startswith("SwapFree:"):
				result['swap_free'] = extract(line)

		if result.has_key('swap_total') and result.has_key('swap_free'):
			result['swap_used'] = result['swap_total'] - result['swap_free']
		if result.has_key('total') and \
			result.has_key('free') and \
			result.has_key('buffers') and \
			result.has_key('cached'):
			result['adjusted_free'] = result['total'] - result['buffers'] - result['cached']

		return result

	def _linux_loadavg(self):
		# TODO: This is very crude. Fix it.
		result = {}

		load_raw = open('/proc/loadavg', 'r').read()
		bits = load_raw.split(' ')

		result['load'] = float(bits[0])
		result['cpus'] = tornado.process.cpu_count()

		return result

class DefaultStatsTest(BaseStatsTest):
	def setUp(self):
		super(DefaultStatsTest, self).setUp()

		self.configuration.plugins.register(
			'paasmaker.stats.default',
			'paasmaker.common.stats.default.DefaultStats',
			{},
			'Default Node Stats generator'
		)

	def test_simple(self):
		plugin = self.configuration.plugins.instantiate(
			'paasmaker.stats.default',
			paasmaker.util.plugin.MODE.NODE_STATS
		)

		stats = {}
		plugin.stats(stats)

		#print json.dumps(stats, indent=4, sort_keys=True)

		self.assertTrue(stats.has_key('platform'), "Missing platform value.")
		self.assertTrue(stats.has_key('memory'), "Missing memory key.")
		self.assertTrue(stats.has_key('load'), "Missing load key.")
		self.assertTrue(stats.has_key('cpus'), "Missing CPUs key.")
		self.assertTrue(stats['cpus'] > 0, "How is your computer working?")
		self.assertTrue(stats['load'] > 0, "Load average seems unusually low.")

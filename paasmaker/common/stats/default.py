
import os
import platform
import ctypes
import json
import re
import subprocess

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
	API_VERSION = "0.9.0"

	def stats(self, existing_stats, callback):
		# Include the platform - this allows score plugins to make
		# more informed decisions.
		existing_stats['platform'] = platform.system()

		if platform.system() == 'Linux':
			existing_stats['load'] = self._linux_loadavg()
			existing_stats.update(self._linux_memory())

		if platform.system() == 'Darwin':
			self.uptime_wrangler = re.compile('load averages?\: ([0-9\.]+)[\, ]+([0-9\.]+)[\, ]+([0-9\.]+)')
			self.darwin_page_count = re.compile('^.+\:\s+(\d+)\.$')

			existing_stats['load'] = self._darwin_loadavg()
			existing_stats['swap_used'] = self._darwin_swap_used()
			existing_stats.update(self._darwin_memory())

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
		existing_stats['cpus'] = tornado.process.cpu_count()

		callback(existing_stats)

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
				result['mem_total'] = extract(line)
			if line.startswith("MemFree:"):
				result['mem_free'] = extract(line)
			if line.startswith("Buffers:"):
				result['mem_buffers'] = extract(line)
			if line.startswith("Cached:"):
				result['mem_cached'] = extract(line)
			if line.startswith("SwapTotal:"):
				result['swap_total'] = extract(line)
			if line.startswith("SwapFree:"):
				result['swap_free'] = extract(line)

		if result.has_key('swap_total') and result.has_key('swap_free'):
			result['swap_used'] = result['swap_total'] - result['swap_free']
		if result.has_key('mem_free') and \
			result.has_key('mem_buffers') and \
			result.has_key('mem_cached'):
			result['mem_adjusted_free'] = result['mem_free'] + result['mem_buffers'] + result['mem_cached']
		else:
			result['mem_adjusted_free'] = result['mem_free']

		return result

	def _linux_loadavg(self):
		load_raw = open('/proc/loadavg', 'r').read()
		bits = load_raw.split(' ')
		return float(bits[0])

	def _darwin_memory(self):
		result = {}

		# page size is also returned in vm_stat, but is basically always 4096
		result['page_size'] = int(paasmaker.util.DarwinSubprocess.check_output(['sysctl', '-n', 'hw.pagesize']))
		result['mem_total'] = int(paasmaker.util.DarwinSubprocess.check_output(['sysctl', '-n', 'hw.memsize']))

		raw_memory = subprocess.check_output("vm_stat")
		raw_memory = raw_memory.split("\n")

		def extract(ln):
			match = self.darwin_page_count.findall(ln)
			return int(match[0]) * result['page_size']

		for line in raw_memory:
			#if line.startswith("Pages wired down:"):
			#	result['mem_wired'] = extract(line)
			#if line.startswith("Pages active:"):
			#	result['mem_active'] = extract(line)
			if line.startswith("Pages free:"):
				result['mem_free'] = extract(line)
			if line.startswith("Pages inactive:"):
				result['mem_inactive'] = extract(line)

		result['mem_adjusted_free'] = result['mem_free'] + result['mem_inactive']

		return result

	def _darwin_swap_used(self):
		raw_swap = paasmaker.util.DarwinSubprocess.check_output(['du', '-ak', '/private/var/vm'])
		raw_swap = raw_swap.split("\n")
		swap_subtotal = 0;

		for line in raw_swap:
			if line.find('swapfile') != -1:
				bits = line.split("\t")
				swap_subtotal += int(bits[0]) * 1024

		return swap_subtotal

	def _darwin_loadavg(self):
		# TODO: performance test me, since this also works on Linux
		uptime_raw = paasmaker.util.DarwinSubprocess.check_output("uptime")
		averages = self.uptime_wrangler.findall(uptime_raw)

		return float(averages[0][0])


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
		plugin.stats(stats, self.stop)
		self.wait()

		#print json.dumps(stats, indent=4, sort_keys=True)

		self.assertTrue(stats.has_key('platform'), "Missing platform value.")
		self.assertTrue(stats.has_key('mem_total'), "Missing total memory value.")
		self.assertTrue(stats.has_key('load'), "Missing 5-min load average value.")
		self.assertTrue(stats.has_key('cpus'), "Missing number of CPUs value.")
		self.assertTrue(stats['cpus'] > 0, "Weird number of CPUs (how is your computer working?!)")
		self.assertTrue(stats['load'] > 0, "Load average seems unusually low.")

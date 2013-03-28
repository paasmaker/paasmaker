#
# Paasmaker - Platform as a Service
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#

import os
import unittest
import platform
import subprocess

from darwinsubprocess import DarwinSubprocess

class ProcessCheck(object):
	@staticmethod
	def is_running(pid, keyword=None):
		"""
		Quickly check to see if a process with the given
		PID is running. To further ensure it is the correct
		process, optionally look for a keyword in the command
		line of the process.

		:arg int pid: The PID to check for.
		:arg str|None keyword: The keyword to search for
			in the command line. It can appear anywhere
			in the command line.
		"""

		if platform.system() == 'Linux':
			pid_path = "/proc/%d/cmdline" % pid

			if os.path.exists(pid_path):
				# Path exists, so now, if supplied, check the keyword.
				if keyword:
					# Load the contents of the cmdline file,
					# and read it's contents, then check it.
					fp = open(pid_path, 'r')
					contents = fp.read()
					fp.close()
					return (keyword in contents)
				else:
					# No keyword supplied to check, so just say
					# "yes, it's running"
					return True
			else:
				# Path does not exist, so process does not exist.
				return False

		if platform.system() == 'Darwin':
			# TODO: this method works on Linux too, but isn't performance-tested
			# (DarwinSubprocess doesn't use check_output because that throws an exception
			# on non-zero exit codes, and `ps` returns exit 1 if -p isn't matched)
			output = DarwinSubprocess.check_output(["ps", "-p", str(pid), "-o", "command="])

			if output:
				if keyword:
					return (keyword in output)
				else:
					return True
			else:
				return False



class ProcessCheckTest(unittest.TestCase):
	def test_simple(self):
		ourpid = os.getpid()

		result = ProcessCheck.is_running(ourpid)
		self.assertTrue(result, "Our process is not running.")

		result = ProcessCheck.is_running(ourpid, "python")
		self.assertTrue(result, "Process is not running or does not have 'python' keyword.")

		result = ProcessCheck.is_running(ourpid, "argh")
		self.assertFalse(result, "Keyword 'argh' matched on our process when it shouldn't have.")

		result = ProcessCheck.is_running(100000)
		self.assertFalse(result, "Found PID 100000 running even though it's an invalid value.")

	def test_create_and_destroy_process(self):
		proc = subprocess.Popen("yes", stdout=subprocess.PIPE)
		pid = proc.pid

		result = ProcessCheck.is_running(pid)
		self.assertTrue(result, ("Created process with pid %d but couldn't find it with is_running" % pid))

		result = ProcessCheck.is_running(pid, "yes")
		self.assertTrue(result, ("Called 'yes' with pid %d but couldn't match command line with is_running" % pid))

		proc.kill()
		unused_output = proc.communicate()

		result = ProcessCheck.is_running(pid)
		self.assertFalse(result, ("Terminated process with pid %d but still found it with is_running" % pid))

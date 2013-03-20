#!/usr/bin/env python

import sys
import json
import subprocess
import os
import fcntl
import datetime
import signal
import urllib2
import time
import httplib

# NOTE: This doesn't use the virtualenv, because it doesn't rely on
# anything inside the virtualenv. If this changes in the future,
# then we will need to start up the virtualenv.

# Expected arguments:
# 1: control file

# Load the control file.
if len(sys.argv) < 2:
	print "No control file provided."
	sys.exit(1)

control_file = sys.argv[1]

if not os.path.exists(control_file):
	print "Provided control file does not exist."
	sys.exit(2)

raw = open(control_file, 'r').read()
try:
	data = json.loads(raw)
except ValueError, ex:
	print "Invalid JSON: %s" % str(ex)
	sys.exit(3)

class CommandSupervisor(object):
	def __init__(self, data):
		self.data = data

		# Open the log file used later.
		self.log_fp = open(data['log_file'], 'a')
		self.log_backlog = []
		self.process_active = False

	def log_helper(self, level, message):
		timestamp = str(datetime.datetime.now())
		formatted_message = "%s %s %s\n" % (timestamp, level, message)
		if self.process_active:
			self.log_backlog.append(formatted_message)
		else:
			self.log_fp.write(formatted_message)
			self.log_fp.flush()

	def signal_handler(self, signum, frame):
		# Attempt to kill our child process.
		self.log_helper("INFO", "Got signal %d" % signum)
		self.kill()

	def sighup_handler(self, signum, frame):
		self.log_helper("INFO", "Ignoring signal %d" % signum)

	def run(self):
		# Prepare to run.
		# NOTE: Assumes that data is as expected...
		instance_id = self.data['instance_id']
		shell = False
		if 'shell' in self.data:
			shell = self.data['shell']
			self.log_helper("INFO", "Using shell mode.")
		pidfile = self.data['pidfile']

		# Install our signal handler.
		signal.signal(signal.SIGTERM, self.signal_handler)

		# And skip SIGHUPs, as that's the whole point of
		# using the command supervisors.
		signal.signal(signal.SIGHUP, signal.SIG_IGN)

		try:
			self.log_helper("INFO", "Running command: %s" % str(self.data['command']))
			self.log_fp.flush()

			# Attempt to disable output buffering.
			# Ref: http://stackoverflow.com/questions/107705/python-output-buffering/1736047#1736047
			fl = fcntl.fcntl(self.log_fp.fileno(), fcntl.F_GETFL)
			fl |= os.O_SYNC
			fcntl.fcntl(self.log_fp.fileno(), fcntl.F_SETFL, fl)

			self.process_active = True
			try:
				self.process = subprocess.Popen(
					self.data['command'],
					stdin=None,
					stdout=self.log_fp,
					stderr=self.log_fp,
					shell=shell,
					cwd=self.data['cwd'],
					env=self.data['environment']
				)

				# Write out OUR pid.
				pid_fd = open(pidfile, 'w')
				pid_fd.write(str(os.getpid()))
				pid_fd.close()

				# Wait for it to complete, or for a signal.
				self.process.wait()

				# Remove the pidfile.
				os.unlink(pidfile)

				return_code = self.process.returncode

			except OSError, ex:
				# Failed to launch, normally because the command
				# was wrong.
				self.log_helper("ERROR", "Failed to start up:")
				self.log_helper("ERROR", str(ex))

				return_code = ex.errno

			# Reopen the log file.
			self.process_active = False
			self.log_fp.close()
			self.log_fp = open(data['log_file'], 'a')
			self.log_fp.write("".join(self.log_backlog))

			# And record the result.
			self.log_helper("INFO", "Completed with result code %d" % return_code)

			# Announce the completion.
			if return_code < 0:
				# It was killed by a signal.
				# But the only signals should have been ours.
				# Consider it as a clean exit.
				return_code = 0

			self.log_helper("INFO", "Real result code %d" % return_code)

			self.announce_completion(return_code)

		except OSError, ex:
			self.log_helper("ERROR", str(ex))

	def kill(self):
		if self.process:
			os.kill(self.process.pid, signal.SIGTERM)
			self.log_helper("INFO", "Sent of SIGTERM signal.")

	def announce_completion(self, code, depth=1):
		self.log_helper("INFO", "Tring to report error code back to heart node.")
		url = "http://localhost:%d/instance/exit/%s/%s/%d" % \
			(self.data['port'], self.data['instance_id'], self.data['exit_key'], code)
		should_retry = False
		try:
			response = urllib2.urlopen(url)
		except urllib2.URLError, ex:
			self.log_helper("ERROR", str(ex))
			should_retry = True
		except httplib.BadStatusLine, ex:
			self.log_helper("ERROR", str(ex))
			should_retry = True
		# Other exceptions should bubble up.

		if should_retry:
			# Retry a few more times.
			if depth < 10:
				self.log_helper("INFO", "Failed to report error code. Will try again in 5s.")
				time.sleep(5)
				self.announce_completion(code, depth + 1)
			else:
				# Ok, give up. What we do instead now is write out a file for later,
				# which the heart can read when it's available again.
				self.log_helper("INFO", "Failed to report error code. Writing to backup file.")
				failed_last_ditch_path = os.path.dirname(self.data['pidfile'])
				failed_last_ditch_path = os.path.join(failed_last_ditch_path, "%s.exited" % self.data['instance_id'])
				open(failed_last_ditch_path, 'w').write(str(code))
		else:
			self.log_helper("INFO", "Successfully reported error code.")

supervisor = CommandSupervisor(data)
supervisor.run()

# Clean up.
if os.path.exists(data['pidfile']):
	os.unlink(data['pidfile'])
if os.path.exists(control_file):
	os.unlink(control_file)
#!/usr/bin/env python

import paasmaker
from paasmaker.util.commandsupervisor import CommandSupervisor
import sys
import json
import subprocess
import os

# Expected arguments:
# 0: program name
# 1: log file
# 2: control file
# 3: optional - configuration file

# TODO: How to capture this output from startup?

# Load the control file.
if len(sys.argv) < 3:
	print "No log and control file provided."
	sys.exit(1)

log_file = sys.argv[1]
control_file = sys.argv[2]

if not os.path.exists(control_file):
	print "Provided control file does not exist."
	sys.exit(2)

raw = open(control_file, 'r').read()
try:
	parsed = json.loads(raw)
except ValueError, ex:
	print "Invalid JSON: %s" % str(ex)
	sys.exit(3)

configuration_files = ['../paasmaker.yml', '/etc/paasmaker/paasmaker.yml']

if len(sys.argv) > 3:
	# Override the configuration from the command line.
	# Used for unit testing.
	configuration_files = [sys.argv[3]]

# Load the configuration.
configuration = paasmaker.common.configuration.Configuration()
configuration.load_from_file(configuration_files)

# Set up the job logger.
paasmaker.util.joblogging.JobLoggerAdapter.setup_joblogger(configuration)

# And launch. This will block until it completes.
supervisor = paasmaker.util.commandsupervisor.CommandSupervisor(configuration, log_file)
supervisor.run(parsed)

# Clean up.
os.unlink(control_file)
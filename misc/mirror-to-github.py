#!/usr/bin/env python

import subprocess
import os

# Important notes:
# - This will keep a clone in the directory you run it in.
#   We don't advise running it in any directory.
# - You can adapt this. The repos listed here are for our use.

REPOS = [
	{
		'symbolic': 'paasmaker-interface-python',
		'source': 'git@bitbucket.org:paasmaker/paasmaker-interface-python.git',
		'target': 'git@github.com:paasmaker/paasmaker-interface-python.git'
	},
	{
		'symbolic': 'paasmaker-interface-php',
		'source': 'git@bitbucket.org:paasmaker/paasmaker-interface-php.git',
		'target': 'git@github.com:paasmaker/paasmaker-interface-php.git'
	},
	{
		'symbolic': 'paasmaker-interface-ruby',
		'source': 'git@bitbucket.org:paasmaker/paasmaker-interface-ruby.git',
		'target': 'git@github.com:paasmaker/paasmaker-interface-ruby.git'
	},
]

def run_helper(command, cwd=None):
	print "Executing %s" % " ".join(command)
	if cwd:
		print "In directory %s" % cwd
	subprocess.check_call(command, cwd=cwd)

for repo in REPOS:
	if not os.path.exists(repo['symbolic']):
		print "Initial setup for %s" % repo['symbolic']

		# Clone it.
		command = ['git', 'clone', '--mirror', repo['source'], repo['symbolic']]
		run_helper(command)

		# Add the remote.
		command = ['git', 'remote', 'add', 'target', repo['target']]
		run_helper(command, cwd=repo['symbolic'])

	# Fetch.
	command = ['git', 'fetch']
	run_helper(command, cwd=repo['symbolic'])

	# Push.
	command = ['git', 'push', '--mirror', 'target']
	run_helper(command, cwd=repo['symbolic'])
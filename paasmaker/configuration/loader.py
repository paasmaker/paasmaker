#!/usr/bin/env python

import yaml
import os
import logging

FILENAME = "paasmaker.yml"

logger = logging.getLogger(__name__)

class Loader:
	def __init__(self):
		self.loadedfile = None

	def get_loaded_filename(self):
		return self.loadedfile

	def locate_file(self, manual_location = None):
		configuration_file = None
		if manual_location:
			logger.debug("Using manual configuration file path %s", manual_location)
			configuration_file = manual_location
		else:
			# Start at cwd, see if we can find the file.
			# If not, go up until we can.
			logger.debug("Testing to see if config exists at %s", FILENAME)
			if os.path.exists(FILENAME):
				configuration_file = FILENAME
			else:
				parent = os.path.dirname(os.getcwd())
				while parent != '':
					test_path = os.path.join(parent, FILENAME)
					logger.debug("Testing to see if config exists at %s", test_path)
					if os.path.exists(test_path):
						configuration_file = test_path
						break
					if parent == os.path.dirname(parent):
						break
					parent = os.path.dirname(parent)
			if not configuration_file:
				global_path = "/etc/paasmaker/" + FILENAME
				logger.debug("Testing to see if config exists at %s", global_path)
				# Try /etc/paasmaker/paasmaker.yml
				if os.path.exists(global_path):
					configuration_file = global_path
		if not configuration_file:
			raise IOError("Can't find a configuration file.")

		logger.debug("Found configuration file %s", configuration_file)
		return configuration_file

	def load(self, manual_location = None):
		contents = open(self.locate_file(manual_location)).read()
		self.loadedfile = manual_location
		values = yaml.load(contents)
		return values


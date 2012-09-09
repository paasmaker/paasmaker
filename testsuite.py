#!/usr/bin/env python

import logging
import unittest
import paasmaker

# Suppress log messages.
# Turning this off temporarily can be helpful for debugging.
logging.basicConfig(level=logging.CRITICAL)

if __name__ == '__main__':
	# Example unit test first.
	suite = unittest.TestLoader().loadTestsFromModule(paasmaker.util.example)

	# Then the utilities.
	suite.addTests(unittest.TestLoader().loadTestsFromModule(paasmaker.util.jsonencoder))
	suite.addTests(unittest.TestLoader().loadTestsFromModule(paasmaker.util.configurationhelper))
	suite.addTests(unittest.TestLoader().loadTestsFromModule(paasmaker.util.joblogging))

	# Configuration system.
	suite.addTests(unittest.TestLoader().loadTestsFromModule(paasmaker.configuration.configuration))
	suite.addTests(unittest.TestLoader().loadTestsFromModule(paasmaker.application.configuration))

	# Database model.
	suite.addTests(unittest.TestLoader().loadTestsFromModule(paasmaker.model))

	# Controllers.
	suite.addTests(unittest.TestLoader().loadTestsFromModule(paasmaker.controller.example))
	suite.addTests(unittest.TestLoader().loadTestsFromModule(paasmaker.controller.information))
	suite.addTests(unittest.TestLoader().loadTestsFromModule(paasmaker.controller.log))
	suite.addTests(unittest.TestLoader().loadTestsFromModule(paasmaker.controller.login))

	# Router.
	suite.addTests(unittest.TestLoader().loadTestsFromModule(paasmaker.router.router))

	# And run them.
	unittest.TextTestRunner(verbosity=2).run(suite)

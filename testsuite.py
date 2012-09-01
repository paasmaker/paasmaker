#!/usr/bin/env python

import logging
import unittest
import paasmaker

# Suppress log messages.
# Turning this off temporarily can be helpful for debugging.
logging.basicConfig(level=logging.CRITICAL)

if __name__ == '__main__':
	suite = unittest.TestLoader().loadTestsFromModule(paasmaker.util.example)
	suite.addTests(unittest.TestLoader().loadTestsFromModule(paasmaker.util.jsonencoder))
	suite.addTests(unittest.TestLoader().loadTestsFromModule(paasmaker.configuration.configuration))
	suite.addTests(unittest.TestLoader().loadTestsFromModule(paasmaker.model))
	suite.addTests(unittest.TestLoader().loadTestsFromModule(paasmaker.controller.example))
	suite.addTests(unittest.TestLoader().loadTestsFromModule(paasmaker.controller.information))
	suite.addTests(unittest.TestLoader().loadTestsFromModule(paasmaker.util.joblogging))
	suite.addTests(unittest.TestLoader().loadTestsFromModule(paasmaker.application.configuration))
	suite.addTests(unittest.TestLoader().loadTestsFromModule(paasmaker.util.configurationhelper))
	suite.addTests(unittest.TestLoader().loadTestsFromModule(paasmaker.controller.log))
	unittest.TextTestRunner(verbosity=2).run(suite)

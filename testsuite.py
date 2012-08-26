#!/usr/bin/env python

import unittest
import paasmaker

if __name__ == '__main__':
	suite = unittest.TestLoader().loadTestsFromModule(paasmaker.util.example)
	suite.addTests(unittest.TestLoader().loadTestsFromModule(paasmaker.util.renderer))
	suite.addTests(unittest.TestLoader().loadTestsFromModule(paasmaker.util.jsonencoder))
	suite.addTests(unittest.TestLoader().loadTestsFromModule(paasmaker.configuration.configuration))
	suite.addTests(unittest.TestLoader().loadTestsFromModule(paasmaker.model))
	suite.addTests(unittest.TestLoader().loadTestsFromModule(paasmaker.controller.example))
	suite.addTests(unittest.TestLoader().loadTestsFromModule(paasmaker.controller.information))
	unittest.TextTestRunner(verbosity=2).run(suite)

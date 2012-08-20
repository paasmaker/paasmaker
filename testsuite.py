#!/usr/bin/env python

import unittest
import paasmaker

if __name__ == '__main__':
	suite = unittest.TestLoader().loadTestsFromModule(paasmaker.util.example)
	suite = unittest.TestLoader().loadTestsFromModule(paasmaker.controller.renderer)
	suite = unittest.TestLoader().loadTestsFromModule(paasmaker.configuration.configuration)
	unittest.TextTestRunner(verbosity=2).run(suite)

#!/usr/bin/env python

#
# Paasmaker - Platform as a Service
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#

import unittest

class Example():
	def num(self, num):
		if num == 2:
			return 1
		else:
			return num

class TestExample(unittest.TestCase):
	def setUp(self):
		self.example = Example()

	def test_num(self):
		self.assertEqual(self.example.num(1), 1)
		self.assertEqual(self.example.num(2), 1)

if __name__ == '__main__':
	unittest.main()


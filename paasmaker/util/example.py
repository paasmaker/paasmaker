#!/usr/bin/env python

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


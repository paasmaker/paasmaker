#!/usr/bin/env python

import json
import datetime
import unittest
import re

class JsonEncoder(json.JSONEncoder):
	def default(self, obj):
		if isinstance(obj, datetime.datetime):
			# Dates are returned in ISO 8601 format, always in UTC.
			# TODO: Convert to UTC!
			return obj.isoformat()
		# TODO: Handle SQLAlchemy objects, including filters.
		return json.JSONEncoder.default(self, obj)

class TestJsonEncoder(unittest.TestCase):
	def test_datetime(self):
		data = {
			'now': datetime.datetime.now(),
			'sub': {
				'subnow': datetime.datetime.now()
			}
		}
		encoded = json.dumps(data, cls=JsonEncoder)
		decoded = json.loads(encoded)
		self.assertTrue(isinstance(decoded['now'], unicode))
		self.assertIsNotNone(re.match('\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{6}', decoded['now']))

if __name__ == '__main__':
	unittest.main()

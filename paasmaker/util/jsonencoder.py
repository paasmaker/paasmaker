import json
import datetime
import unittest
import re
import paasmaker

class JsonEncoder(json.JSONEncoder):
	def default(self, obj):
		if isinstance(obj, datetime.datetime):
			# Dates are returned in ISO 8601 format, always in UTC.
			# TODO: Convert to UTC!
			return obj.isoformat()
		if isinstance(obj, paasmaker.model.OrmBase):
			# These classes know how to flatten themselves.
			# TODO: Pass a possibly mutatable list of fields to return.
			return obj.flatten()
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

	def test_orm(self):
		# TODO: Not working here - something to do with SQLAlchemy
		# not being set up fully. This is tested in the unit tests
		# for the models instead.
		pass


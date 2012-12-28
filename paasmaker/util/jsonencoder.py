import json
import datetime
import unittest
import re
import paasmaker
import sqlalchemy

class JsonEncoder(json.JSONEncoder):
	"""
	Slightly enhanced JSON encoder that knows how to encode
	a few additional types than the default Python JSON encoder.

	The following types are handled by this encoder:

	* **datetime**: returns the date in ISO8601 format, in UTC.
	* **set**: Considers the set as a list.
	* **OrmBase**: Flattens the ORM objects using their ``flatten()`` method, returning the results.
	* **sqlalchemy.orm.query.Query**: flattens into a list, and then processes the results as above.

	To use it, just specify it as the encoder when encoding::

		result = json.dumps(data, cls=paasmaker.util.jsonencoder.JsonEncoder)

	"""
	def default(self, obj):
		if isinstance(obj, datetime.datetime):
			# Dates are returned in ISO 8601 format, always in UTC.
			# TODO: Convert to UTC!
			return obj.isoformat()
		if isinstance(obj, set):
			return list(obj)
		if isinstance(obj, paasmaker.model.OrmBase):
			# These classes know how to flatten themselves.
			# TODO: Pass a possibly mutatable list of fields to return.
			return obj.flatten()
		if isinstance(obj, sqlalchemy.orm.query.Query):
			# Flatten the query into objects.
			flat = []
			for item in obj:
				flat.append(item)
			return flat
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


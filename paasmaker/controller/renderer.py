#!/usr/bin/env python

from mako.lookup import TemplateLookup
import datetime
import simplejson as json
import unittest

class Renderer:
	def __init__(self, templatedir):
		self.template_lookup = TemplateLookup(directories=[templatedir])
		self.data = {}
		self.types = {}
		self.format = 'html'

	def add_data(self, name, value):
		self.data[name] = value
		self.types[name] = 'data'

	def add_data_list(self, name, value):
		self.data[name] = value
		self.types[name] = 'data-list'

	def add_data_template(self, name, value):
		self.data[name] = value
		self.types[name] = 'template'

	def prepare_to_json(self, data):
		if data == None:
			return None
		elif isinstance(data, dict):
			result = {}
			for key in data:
				result[key] = self.prepare_to_json(data[key])
			return result
		elif isinstance(data, list):
			result = []
			for item in data:
				result.append(self.prepare_to_json(item))
			return result
		elif isinstance(data, datetime.datetime):
			# Return dates in ISO 8601 format. Always in UTC.
			return data.isoformat()
		elif isinstance(data, int) or isinstance(data, float) or isinstance(data, bool):
			return data
		else:
			return str(data)

	def get_format(self):
		return self.format

	def set_format(self, format):
		if format != 'json' and format != 'html':
			raise ValueError("Invalid format '%s' supplied." % format)
		self.format = format

	def render(self, template_name):
		# Determine the mode from the parameters.
		if self.get_format() == 'html':
			template = self.template_lookup.get_template(template_name)
			return template.render(**self.data)
		elif self.get_format() == 'json':
			# Filter the data. Only data/data-list go out.
			outputdata = {}
			for key, value in self.data.iteritems():
				if self.types[key] == 'data' or self.types[key] == 'data-list':
					outputdata[key] = self.prepare_to_json(value)
			return json.dumps(outputdata)
		else:
			# Not a supported mode.
			return None


class TestRenderer(unittest.TestCase):

	def setUp(self):
		self.ren = Renderer('templates')

	def test_format_choose(self):
		self.assertEqual('html', self.ren.get_format(), 'Format is not HTML')
		self.ren.set_format('json')
		self.assertEqual('json', self.ren.get_format(), 'Format is not JSON')
		self.assertRaises(ValueError, self.ren.set_format, 'other')

	def _make_format_tester(self):
		self.ren.add_data('test', 1);
		self.ren.add_data_list('testList', [2])
		self.ren.add_data_template('template', 3)

	def test_json_format(self):
		self.ren.set_format('json')
		self._make_format_tester()

		result = self.ren.render('tests/renderer.html')
		parsed = json.loads(result)
		self.assertTrue(parsed.has_key('test'), "JSON does not contain 'test' key.")
		self.assertTrue(parsed.has_key('testList'), "JSON does not contain 'testList' key.")
		self.assertIsInstance(parsed['testList'], list, "JSON testList is not a list.")
		self.assertFalse(parsed.has_key('template'), "JSON contains template-only key.")

	def test_html_format(self):
		self.ren.set_format('html')
		self._make_format_tester()

		result = self.ren.render('tests/renderer.html')
		self.assertIn('1', result, "HTML does not contain first key.")
		self.assertIn('2', result, "HTML does not contain second key.")
		self.assertIn('3', result, "HTML does not contain third key.")

if __name__ == '__main__':
	unittest.main()

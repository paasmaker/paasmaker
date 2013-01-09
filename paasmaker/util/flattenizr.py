
import json
import unittest

# What does this class do? It converts nested dicts and
# lists to or from a flat representation.
# Doesn't Colander do this? Yes, it does, but it's strictly
# based on Schemas. Sometimes you want to pass back arbitrary
# maps, and Colander won't let you do this. Also, the unflatten
# requires lists of fixed lengths, which doesn't solve all
# cases when passing data via HTTP key/value pairs.

# So, given this input:
# {
#   'foo': 'bar',
#   'baz': {
#      'sub': 'one'
#   },
#   'bar': [1, 2],
#   'foo2': [
#      {'a': 'b', 'c': 'd'},
#      {'e': 'f'}
#   ]
# }
# Should flatten to:
# ---
# foo: bar
# baz.sub: one
# bar.0: 1
# bar.0: 2
# foo2.0.a: b
# foo2.0.c: d
# foo2.1.e: f
# ---
# And reverse as appropriate.
# Note that we treat values as strings, dicts, or lists
# only. It's up to whatever handles this data to make
# the correct distinction. The numbers for arrays are
# irrelevant; they're just to distinguish between different
# elements in the array (so you could alternate between
# zero and one and have them come out)

class Flattenizr(object):

	def flatten(self, structure, flat_arrays=False):
		result = []
		self._flatten_into('', structure, result, flat_arrays)
		return result

	def _flatten_into(self, prefix, structure, result, flat_arrays=False):
		real_prefix = ''
		if prefix != "":
			real_prefix = "%s." % prefix
		if isinstance(structure, dict):
			for k, v in structure.iteritems():
				self._flatten_into("%s%s" % (real_prefix, k), v, result, flat_arrays)
		elif isinstance(structure, list):
			for i in range(len(structure)):
				if flat_arrays:
					index_key = "[]"
				else:
					index_key = "%d" % i
				self._flatten_into("%s%s" % (real_prefix, index_key), structure[i], result, flat_arrays)
		else:
			# Convert to string, and it belongs in this prefix.
			result.append((prefix, str(structure)))

	def unflatten(self, input_keys):
		result = {}
		# TODO: Implement...
		return result

class FlatterizrTest(unittest.TestCase):
	def test_unflatten(self):
		#return
		flat = [
			('foo', 'bar'),
			('baz.sub', 'one'),
			('bar.0', '1'),
			('bar.1', '2'),
			('foo2.0.a', 'b'),
			('foo2.0.c', 'd'),
			('foo2.1.e', 'f')
		]

		ftzr = Flattenizr()
		unflat = ftzr.unflatten(flat)

		#print json.dumps(unflat, indent=4, sort_keys=True)

	def test_flatten(self):
		struct = {
			'foo': 'bar',
			'baz': {
				'sub': 'one'
				},
			'bar': [1, 2],
			'foo2': [
				{'a': 'b', 'c': 'd'},
				{'e': 'f'}
			]
		}

		ftzr = Flattenizr()
		flat = ftzr.flatten(struct)

		#print json.dumps(flat, indent=4, sort_keys=True)
		self.assertEquals(len(flat), 7, "Not the expected number of entries.")

		# Flatten with no array indexes.
		flat = ftzr.flatten(struct, True)
		#print json.dumps(flat, indent=4, sort_keys=True)
		self.assertEquals(len(flat), 7, "Not the expected number of entries.")
		self.assertIn('[]', flat[0][0])
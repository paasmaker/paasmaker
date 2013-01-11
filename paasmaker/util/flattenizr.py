
import json
import unittest

# TODO: Handle invalid data better (raise exceptions when inputs are not
# expected formats)
# TODO: Update the documentation to pull in the unit test values.
# TODO: Test around situations with large data payloads. There must be
# a DOS attack somewhere in this code.

class Flattenizr(object):
	"""
	Convert nested lists and dicts between flat and normal
	representations.

	Why are we doing this? Because HTTP post bodies contain
	key value pairs, which isn't nested data structures. So this
	class can convert key value pairs to nested dicts based
	on simple hints from the keys. This allows controllers to work
	the same way whether given a JSON body or a HTTP post body,
	and enable the same features.

	Doesn't something already implement this? Colander does - but
	it's strictly schema based. If your keys are not defined in the
	colander schema, they don't end up in the flattened or unflattened
	versions. Sometimes this is what you want; and other times there
	are a few types of structures that you can't define with Colander
	which leaves you without the data you wanted.

	Peppercorn is another library used to do something similar. However,
	the syntax for the key/value pairs is not as natural as the output
	of Colander's flatten, and as such a little bit harder to work with
	on the client side; especially if you're creating form elements
	with JavaScript.

	This class also contains a method to compare two data structures.
	Internally, it does that by flattening them, and then testing their
	keys. This is an easy way to test arbitrarily nested data structures.
	"""

	# Method constants for the comparison.
	EXACT = 1
	NORMAL = 2

	def flatten(self, structure, flat_arrays=False):
		"""
		Flatten the given data structure into key/value pairs.

		In a nutshell, this::

			{
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

		Will become this::

			[
				["bar.0", "1"],
				["bar.1", "2"],
				["foo", "bar"],
				["baz.sub", "one"],
				["foo2.0.a", "b"],
				["foo2.0.c", "d"],
				["foo2.1.e", "f"]
			]

		And if you pass true for flat_arrays, the result is as follows. This
		is designed to result in an output that can be used to compare two
		nested data structures. Note that this output can't always be unflattened
		to result in the original data structure.::

			[
				["bar.[]", "1"],
				["bar.[]", "2"],
				["foo", "bar"],
				["baz.sub", "one"],
				["foo2.[].a", "b"],
				["foo2.[].c", "d"],
				["foo2.[].e", "f"]
			]

		:arg dict structure: The structure to flatten.
		:arg bool flat_arrays: If true, flatten array indexes to an anonymous
			value, used for comparing data structures.
		"""
		result = []
		self._flatten_into('', structure, result, flat_arrays)
		return result

	def _flatten_into(self, prefix, structure, result, flat_arrays=False):
		# Recursive helper function to convert part of the structure.
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
		"""
		Take a flattened data structure (possibly from a HTTP POST)
		and convert it into a nested data structure.

		Given this input::

			[
				('foo', 'bar'),
				('baz.sub', 'one'),
				('bar.0', '1'),
				('bar.1', '2'),
				('bar.[]', '3'),
				('foo2.0.a', 'b'),
				('foo2.0.c', 'd'),
				('foo2.1.e', 'f'),
				('foo3.[].a', 'b'),
				('foo3.[].c', 'd'),
				# The following should result in three
				# entries in the list - the idea is that
				# the numbers don't have to be sequential,
				# just the same to match up the data - this makes
				# it much easier on the front end - you can skip
				# indicies to omit them, for example.
				('foo4.0.a', 'b'),
				('foo4.1.c', 'd'),
				('foo4.1.e', 'f'),
				('foo4.0.g', 'g'),
				('foo5.0.0', 'one'),
				('foo5.0.1', 'two'),
				('foo5.1.0', 'three'),
				('foo5.1.1', 'four'),
			]

		Will result in this data structure::

			{
				"bar": ["1", "2", "3"],
				"baz": {
					"sub": "one"
				},
				"foo": "bar",
				"foo2": [
					{
						"a": "b",
						"c": "d"
					},
					{
						"e": "f"
					}
				],
				"foo3": [
					{
						"a": "b"
					},
					{
						"c": "d"
					}
				],
				"foo4": [
					{
						"a": "b"
					},
					{
						"c": "d",
						"e": "f"
					},
					{
						"g": "g"
					}
				],
				"foo5": [
					["one", "two"],
					["three", "four"]
				]
			}
		"""
		result = {}
		last_indexes = {}
		for key, value in input_keys:
			path = key.split(".")
			self._unflatten_path(result, path, value, last_indexes)

		return result

	def _unflatten_path(self, container, path, value, last_indexes):
		# Helper recursive function to unflatten part of the data tree.
		if len(path) == 1:
			# This is the end.
			if self._is_list_index(path[0]):
				container.append(value)
			else:
				container[path[0]] = value
		else:
			# It's longer. Determine the container
			# for this section of path, then continue.
			is_list_index = self._is_list_index(path[0])

			if isinstance(container, dict):
				path_key = path[0]

				if not container.has_key(path_key):
					# Peek ahead. If the next part
					# of the path is a list, make it a list.
					if self._is_list_index(path[1]):
						container[path_key] = []
					else:
						container[path_key] = {}

				sub_container = container[path_key]
			elif isinstance(container, list):
				# Peek ahead. If the next part of the path
				# is a list, make it a list. Otherwise, it's a dict.
				if self._is_list_index(path[1]):
					sub_container = []
				else:
					sub_container = {}

				if path[0].isdigit():
					# See if this index is the same as last time.
					# If so, we use the same list as last time.
					index_key = str(id(container))
					if not last_indexes.has_key(index_key):
						# Use a dummy index, to allow the code below
						# to work.
						last_indexes[index_key] = (-1, sub_container)

					if path[0] == last_indexes[index_key][0]:
						# Yes, it's the same as last time.
						# Use the same container, and select the last index.
						sub_container = last_indexes[index_key][1]
					else:
						# New index. Create a new container.
						last_indexes[index_key] = (path[0], sub_container)
						container.append(sub_container)
				else:
					container.append(sub_container)

			self._unflatten_path(sub_container, path[1:], value, last_indexes)

	def _is_list_index(self, key):
		# Check if the given key is a list index.
		if key == '[]':
			return True
		return key.isdigit()

	def compare(self, a, b, method=NORMAL):
		"""
		Compare the two data structures. Internally works
		by flattening the data structures and then comparing
		the keys. The method controls how the comparison is
		done.

		Caution: arrays are flattened into anonymous arrays. This
		means that these two structures will be considered equal::

			TODO: Generate sample data structures.

		When using the normal method, the structures are
		considered equal if all the keys in ``b`` exist in ``a``
		and the values are the same. ``a`` can have more keys
		than ``b``. If ``b`` has no keys, it's considered a match
		regardless of what's in ``a``.

		When using the exact method, the structures are considered
		equal if they both have exactly the same number of keys,
		and all keys and values are identical.

		:arg dict a: The structure to compare against.
		:arg dict b: The other structure to compare.
		"""

		flat_a = self.flatten(a, flat_arrays=True)
		flat_b = self.flatten(b, flat_arrays=True)

		# Now flatten into key=value strings.
		flat_kv_a = self._to_key_equals_value(flat_a)
		flat_kv_b = self._to_key_equals_value(flat_b)

		if method == Flattenizr.EXACT:
			return self._compare_exact(flat_kv_a, flat_kv_b)
		elif method == Flattenizr.NORMAL:
			return self._compare_normal(flat_kv_a, flat_kv_b)
		else:
			raise ValueError("Invalid comparison method supplied.")

	def _to_key_equals_value(self, flat):
		# Further flatten [key, value] pairs into an array
		# of key=value strings.
		output = []
		for key, value in flat:
			output.append("%s=%s" % (key, value))

		return output

	def _compare_exact(self, flat_a, flat_b):
		# Short circuit: if the number of keys doesn't match,
		# then it won't match.
		if len(flat_a) != len(flat_b):
			return False

		# Check ALL the keys.
		for kv in flat_a:
			if kv not in flat_b:
				return False

		return True

	def _compare_normal(self, flat_a, flat_b):
		# Short circuit: if B is empty, it matches.
		if len(flat_b) == 0:
			return True

		# Check that all the keys in B exist in A.
		match = True
		for kv in flat_b:
			if kv not in flat_a:
				match = False

		return match


class FlattenizrTest(unittest.TestCase):
	def test_unflatten(self):
		#return
		flat = [
			('foo', 'bar'),
			('baz.sub', 'one'),
			('bar.0', '1'),
			('bar.1', '2'),
			('bar.[]', '3'),
			('foo2.0.a', 'b'),
			('foo2.0.c', 'd'),
			('foo2.1.e', 'f'),
			('foo3.[].a', 'b'),
			('foo3.[].c', 'd'),
			# The following should result in three
			# entries in the list - the idea is that
			# the numbers don't have to be sequential,
			# just the same to match up the data.
			('foo4.0.a', 'b'),
			('foo4.1.c', 'd'),
			('foo4.1.e', 'f'),
			('foo4.0.g', 'g'),
			('foo5.0.0', 'one'),
			('foo5.0.1', 'two'),
			('foo5.1.0', 'three'),
			('foo5.1.1', 'four'),
		]

		ftzr = Flattenizr()
		unflat = ftzr.unflatten(flat)

		#print json.dumps(unflat, indent=4, sort_keys=True)
		self.assertTrue(unflat.has_key('foo'))
		self.assertTrue(unflat.has_key('bar'))
		self.assertTrue(unflat.has_key('baz'))
		self.assertTrue(unflat.has_key('foo2'))
		self.assertEquals(len(unflat['foo2']), 2)
		self.assertEquals(len(unflat['bar']), 3)
		self.assertTrue(unflat['foo2'][0].has_key('a'))
		self.assertTrue(unflat['foo2'][0].has_key('c'))
		self.assertFalse(unflat['foo2'][0].has_key('e'))
		self.assertTrue(unflat['foo2'][1].has_key('e'))
		self.assertFalse(unflat['foo2'][1].has_key('a'))
		self.assertEquals(len(unflat['foo3']), 2)
		self.assertTrue(unflat['foo3'][0].has_key('a'))
		self.assertFalse(unflat['foo3'][0].has_key('c'))
		self.assertTrue(unflat['foo3'][1].has_key('c'))
		self.assertFalse(unflat['foo3'][1].has_key('a'))

		self.assertEquals(len(unflat['foo4']), 3)
		self.assertTrue(unflat['foo4'][0].has_key('a'))
		self.assertFalse(unflat['foo4'][0].has_key('c'))
		self.assertTrue(unflat['foo4'][1].has_key('c'))
		self.assertFalse(unflat['foo4'][1].has_key('a'))
		self.assertFalse(unflat['foo4'][1].has_key('g'))
		self.assertTrue(unflat['foo4'][2].has_key('g'))
		self.assertFalse(unflat['foo4'][2].has_key('e'))

		self.assertEquals(len(unflat['foo5']), 2)
		self.assertEquals(len(unflat['foo5'][0]), 2)
		self.assertEquals(unflat['foo5'][0][0], "one")
		self.assertEquals(len(unflat['foo5'][1]), 2)
		self.assertEquals(unflat['foo5'][1][0], "three")

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

		# Unflatten it again.
		unflat = ftzr.unflatten(flat)
		#print json.dumps(unflat, indent=4, sort_keys=True)
		self.assertEquals(len(unflat), 4, "Not the expected number of entries.")

		# Flatten with no array indexes.
		flat = ftzr.flatten(struct, True)
		#print json.dumps(flat, indent=4, sort_keys=True)
		self.assertEquals(len(flat), 7, "Not the expected number of entries.")
		self.assertIn('[]', flat[0][0])

	def test_compare_normal(self):
		example_a = {
			"node": {},
			"roles": {
				"heart": True,
				"pacemaker": True,
				"router": True
			},
			"runtimes": {
				"paasmaker.runtime.ruby.rbenv": [
					"1.9.3",
					"1.9.3-p327"
				],
				"paasmaker.runtime.shell": [
					"1"
				]
			}
		}

		example_b_match_list = {
			"runtimes": {
				"paasmaker.runtime.ruby.rbenv": [
					"1.9.3",
					"1.9.3-p327"
				]
			}
		}

		example_b_nomatch_list = {
			"runtimes": {
				"paasmaker.runtime.ruby.rbenv": [
					"1.9.2"
				]
			}
		}

		example_b_nomatch_list_2 = {
			"runtimes": {
				"paasmaker.runtime.ruby.rbenv": [
					"1.9.2",
					"1.9.3-p327"
				]
			}
		}

		example_b_match_tag = {
			"roles": {
				"heart": True
			}
		}

		example_b_nomatch_tag = {
			"roles": {
				"foo": True
			}
		}

		example_b_empty = {}

		ftzr = Flattenizr()

		self.assertTrue(
			ftzr.compare(example_a, example_b_match_list),
			"Couldn't match a list."
		)
		self.assertFalse(
			ftzr.compare(example_a, example_b_nomatch_list),
			"Incorrectly matched a list."
		)
		self.assertFalse(
			ftzr.compare(example_a, example_b_nomatch_list_2),
			"Incorrectly matched a list."
		)

		self.assertTrue(
			ftzr.compare(example_a, example_b_match_tag),
			"Couldn't match a tag."
		)
		self.assertFalse(
			ftzr.compare(example_a, example_b_nomatch_tag),
			"Incorrectly matched a tag."
		)

		self.assertTrue(
			ftzr.compare(example_a, example_b_empty),
			"Didn't match an empty target set."
		)
		self.assertFalse(
			ftzr.compare(example_b_empty, example_a),
			"Matched tags in B when A is empty."
		)

	def test_compare_exact(self):
		example_a = {
			"test": "bar"
		}

		example_b_match = {
			"test": "bar"
		}

		example_b_nomatch = {
			"test": "baz"
		}

		example_b_nomatch_2 = {
			"foo": "bar"
		}

		example_b_empty = {}

		ftzr = Flattenizr()

		self.assertTrue(
			ftzr.compare(example_a, example_b_match, method=Flattenizr.EXACT),
			"Should have matched."
		)

		self.assertFalse(
			ftzr.compare(example_a, example_b_nomatch, method=Flattenizr.EXACT),
			"Should not have matched."
		)

		self.assertFalse(
			ftzr.compare(example_a, example_b_nomatch_2, method=Flattenizr.EXACT),
			"Should not have matched."
		)

		self.assertFalse(
			ftzr.compare(example_a, example_b_empty, method=Flattenizr.EXACT),
			"Should not have matched."
		)

		self.assertFalse(
			ftzr.compare(example_b_empty, example_a, method=Flattenizr.EXACT),
			"Should not have matched."
		)
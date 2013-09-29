#
# Paasmaker - Platform as a Service
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#

class CallbackProcessList(object):
	"""
	Take a list of items, and call the supplied process callback for
	each entry. The object then handles moving onto the next entry.
	This is designed to work with asynchronous callbacks, which otherwise
	make handling lists in sequence harder.

	This is to save some boilerplate code that appears over the place
	to basically do the same thing.

	The supplied callback is called in order of the entries on the list.

	Here is an example of how to use it:

	.. code-block:: python

		my_list = [1, 2, 3]

		def entry_handler(entry, processor):
		    # Handle your action here.
		    def async_callback():
		        # To move onto next...
		        processor.next()

		    launch_async_thingy(callback=async_callback)

		def done_handler():
		    # All entries are complete now.
		    pass

		processor = CallbackProcessList(my_list, entry_handler, done_handler)
		processor.start()

	:arg list target_list: The list to iterate over. A copy is taken
		of the list so that the original list is untouched.
	:arg callable process_callback: A callback called with two arguments:
		the current entry on the list, and a reference to this object.
	:arg callable nomore_callback: The callback called when no more entries
		are available.
	"""

	def __init__(self, target_list, process_callback, nomore_callback):
		# Take a copy of the list.
		self.target_list = list(target_list)
		# And we need a copy because we reverse it...
		self.target_list.reverse()

		self.process_callback = process_callback
		self.nomore_callback = nomore_callback

	def start(self):
		"""
		Start processing entries on the list.
		"""
		self.next()

	def next(self):
		"""
		Move onto the next item in the list.
		"""
		try:
			# Get the next item.
			current = self.target_list.pop()

			self.process_callback(current, self)

		except IndexError, ex:
			# No more items.
			# Call the no more callback, if supplied.
			if self.nomore_callback is not None:
				self.nomore_callback()

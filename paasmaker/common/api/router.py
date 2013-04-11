#
# Paasmaker - Platform as a Service
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#

import logging

import paasmaker
from apirequest import APIRequest, StreamAPIRequest, APIResponse

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

class RouterStreamAPIRequest(StreamAPIRequest):

	def stats(self, name, input_id):
		"""
		Get raw stats for the given name and input ID.

		For example, you might send name 'workspace' and input_id '1'
		to fetch the latest stats for workspace ID 1. This will emit
		a router.stats.update event once with the stats. If you want
		another update, call this function again.

		:arg str name: The name of the stats to fetch.
		:arg str|int input_id: The input ID for the name.
		"""
		self.emit('router.stats.update', {'name': name, 'input_id': input_id})

	def history(self, name, input_id, metric, start, end=None):
		"""
		Fetch router stats history.

		:arg str name: The name to fetch the history for.
		:arg str|int input_id: The input ID for the name.
		:arg str|list metric: The metric to fetch (eg, 'requests') or a list to fetch.
		:arg int start: The unix timestamp to fetch from.
		:arg int|None end: The unix timestamp to fetch to.
		"""
		self.emit('router.history.update', {'name': name, 'input_id': input_id, 'metric': metric, 'start': start, 'end': end})

	def set_history_callback(self, callback):
		"""
		Set the callback for when new history data is available.

		The signature looks as follows:

		.. code-block:: python

			def history(name, input_id, start, end, values):
				# values is a dict of lists:
				# { 'requests': [[unixtimestamp, value], ...] }
				pass
		"""
		self.on('router.history.update', callback)

	def set_stats_error_callback(self, callback):
		"""
		Set the callback for when an router stats error occurs.

		The callback looks like so:

		.. code-block:: python

			def error(message, exception=None, name=None, input_id=None):
				pass
		"""
		self.on('router.stats.error', callback)

	def set_history_error_callback(self, callback):
		"""
		Set the callback for when an router history error occurs.

		The callback looks like so:

		.. code-block:: python

			def error(message, exception=None, name=None, input_id=None):
				pass
		"""
		self.on('router.history.error', callback)

	def set_update_callback(self, callback):
		"""
		Sets the callback called when an update is ready.

		The callback looks like this:

		.. code-block:: python

			def update(name, input_id, stats):
				# stats is a dict of stats.
				pass

		"""
		self.on('router.stats.update', callback)

class RouterTableDumpAPIRequest(APIRequest):
	"""
	Dump information on the router table.
	"""
	def __init__(self, *args, **kwargs):
		super(RouterTableDumpAPIRequest, self).__init__(*args, **kwargs)
		self.method = 'GET'

	def get_endpoint(self):
		return '/router/dump'
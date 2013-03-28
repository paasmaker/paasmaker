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

class JobAbortAPIRequest(APIRequest):
	"""
	Send an abort request to a specific job ID.
	"""
	def __init__(self, *args, **kwargs):
		super(JobAbortAPIRequest, self).__init__(*args, **kwargs)
		self.method = 'GET'
		self.job_id = None

	def set_job(self, job_id):
		"""
		Set the ID of the job to abort.

		:arg str job_id: The job ID to abort.
		"""
		self.job_id = job_id

	def get_endpoint(self):
		return '/job/abort/%s' % self.job_id

class JobStreamAPIRequest(StreamAPIRequest):

	def subscribe(self, job_id):
		"""
		Subscribe to the given job ID, and also it's entire tree.
		As soon as the subscribe request is processed, the server will
		send back a job.subscribed event, with a list of jobs that
		you are now listening to, and also a job.tree event that contains
		the current entire state of the job tree.

		While you are subscribed, you are sent job.status and job.new
		updates for the entire job tree, until you unsubscribe or disconnect.

		:arg str job_id: The job to subscribe to.
		"""
		logging.debug("Subscribing to %s", job_id)
		self.emit('job.subscribe', {'job_id': job_id})

	def unsubscribe(self, job_id):
		"""
		Unsubscribe from the given job ID. This will stop further updates
		from being sent through to you.

		:arg str job_id: The job to unsubscribe from.
		"""
		logging.debug("Unsubscribing from %s", job_id)
		self.emit('job.unsubscribe', {'job_id': job_id})

	def set_subscribed_callback(self, callback):
		"""
		Set a callback called when the subscribe request has been
		processed by the remote server. The callback is as so::

			def subscribed(jobs):
				# jobs is a list of all jobs in the tree
				pass
		"""
		self.on('job.subscribed', callback)

	def set_status_callback(self, callback):
		"""
		Set a callback called when a subscribed job changes status.
		The callback signature is as follows::

			def status(job_id, job_data):
				# job_data is a dict of values about the job.
				pass
		"""
		self.on('job.status', callback)

	def set_new_callback(self, callback):
		"""
		Set a callback called when one of the subscribed jobs has a new
		child job. The signature is as follows::

			def new(job_data):
				# job_data is a dict of values about the new job.
				# use key 'parent_id' to figure out the jobs parent.
				pass
		"""
		self.on('job.new', callback)

	def set_tree_callback(self, callback):
		"""
		Set a callback called when the entire job tree is sent through.
		This happens immediately after you subscribe to a job, so you can
		start with a known job tree state. The signature is as follows::

			def tree(job_id, tree):
				# tree is a dict. It contains data about the root job.
				# Each dict contains a key called 'children' that is
				# a list of dicts of children of that job.
				pass
		"""
		self.on('job.tree', callback)

import logging

import paasmaker
from apirequest import APIRequest, APIResponse

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

class VersionGetAPIRequest(APIRequest):
	"""
	Fetch information on a version of an application.
	"""
	def __init__(self, *args, **kwargs):
		super(VersionGetAPIRequest, self).__init__(*args, **kwargs)
		self.version_id = None
		self.method = 'GET'

	def set_version(self, version_id):
		"""
		Set the version ID to fetch.

		:arg int version_id: The version ID to fetch.
		"""
		self.version_id = version_id

	def get_endpoint(self):
		return '/version/%d' % self.version_id

class VersionInstancesAPIRequest(APIRequest):
	"""
	Fetch a list of instances for a given version ID.
	"""
	def __init__(self, *args, **kwargs):
		super(VersionInstancesAPIRequest, self).__init__(*args, **kwargs)
		self.version_id = None
		self.method = 'GET'

	def set_version(self, version_id):
		"""
		Set the version ID to fetch.

		:arg int version_id: The version ID to fetch.
		"""
		self.version_id = version_id

	def get_endpoint(self):
		return '/version/%d/instances' % self.version_id

class VersionActionRootAPIRequest(APIRequest):
	"""
	A base class for version mutate requests. You won't work
	with this directly, but with one of it's subclasses.

	Each of the requests will return a job ID, that you
	can use to track the progress of that request.
	"""
	def __init__(self, *args, **kwargs):
		self.version_id = None
		super(VersionActionRootAPIRequest, self).__init__(*args, **kwargs)

	def set_version(self, version_id):
		"""
		Set the version ID to work on.
		"""
		self.version_id = version_id

class VersionRegisterAPIRequest(VersionActionRootAPIRequest):
	"""
	Ask the server to register a version onto the nodes.
	"""
	def get_endpoint(self):
		return '/version/%d/register' % self.version_id

class VersionStartAPIRequest(VersionActionRootAPIRequest):
	"""
	Ask the server to start a version of the application.
	"""
	def get_endpoint(self):
		return '/version/%d/start' % self.version_id

class VersionStopAPIRequest(VersionActionRootAPIRequest):
	"""
	Ask the server to stop a version of the application.
	"""
	def get_endpoint(self):
		return '/version/%d/stop' % self.version_id

class VersionDeRegisterAPIRequest(VersionActionRootAPIRequest):
	"""
	Ask the server to de-register a version of the application.
	"""
	def get_endpoint(self):
		return '/version/%d/deregister' % self.version_id

class VersionSetCurrentAPIRequest(VersionActionRootAPIRequest):
	"""
	Ask the server to set a version as the current version
	for the application.
	"""
	def get_endpoint(self):
		return '/version/%d/setcurrent' % self.version_id

class VersionDeleteAPIRequest(VersionActionRootAPIRequest):
	"""
	Ask the server to delete a version of the application so
	it can no longer be started.
	"""
	def get_endpoint(self):
		return '/version/%d/delete' % self.version_id
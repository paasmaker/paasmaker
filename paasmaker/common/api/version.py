
import paasmaker
import logging

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

class VersionGetAPIRequest(paasmaker.util.APIRequest):
	def __init__(self, *args, **kwargs):
		super(VersionGetAPIRequest, self).__init__(*args, **kwargs)
		self.version_id = None
		self.method = 'GET'

	def set_version(self, version_id):
		self.version_id = version_id

	def get_endpoint(self):
		return '/version/%d' % self.version_id

class VersionInstancesAPIRequest(paasmaker.util.APIRequest):
	def __init__(self, *args, **kwargs):
		super(VersionInstancesAPIRequest, self).__init__(*args, **kwargs)
		self.version_id = None
		self.method = 'GET'

	def set_version(self, version_id):
		self.version_id = version_id

	def get_endpoint(self):
		return '/version/%d/instances' % self.version_id
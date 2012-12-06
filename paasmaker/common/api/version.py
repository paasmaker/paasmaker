
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

class VersionActionRootAPIRequest(paasmaker.util.APIRequest):
	def __init__(self, *args, **kwargs):
		self.version_id = None
		super(VersionActionRootAPIRequest, self).__init__(*args, **kwargs)

	def set_version(self, version_id):
		self.version_id = version_id

class VersionRegisterAPIRequest(VersionActionRootAPIRequest):
	def get_endpoint(self):
		return '/version/%d/register' % self.version_id

class VersionStartAPIRequest(VersionActionRootAPIRequest):
	def get_endpoint(self):
		return '/version/%d/start' % self.version_id

class VersionStopAPIRequest(VersionActionRootAPIRequest):
	def get_endpoint(self):
		return '/version/%d/stop' % self.version_id

class VersionDeRegisterAPIRequest(VersionActionRootAPIRequest):
	def get_endpoint(self):
		return '/version/%d/deregister' % self.version_id

class VersionSetCurrentAPIRequest(VersionActionRootAPIRequest):
	def get_endpoint(self):
		return '/version/%d/setcurrent' % self.version_id
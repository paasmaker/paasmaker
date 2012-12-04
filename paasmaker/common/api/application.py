
import paasmaker
import logging

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

class ApplicationGetAPIRequest(paasmaker.util.APIRequest):
	def __init__(self, *args, **kwargs):
		super(ApplicationGetAPIRequest, self).__init__(*args, **kwargs)
		self.application_id = None
		self.method = 'GET'

	def set_application(self, application_id):
		self.application_id = application_id

	def get_endpoint(self):
		return '/application/%d' % self.application_id

class ApplicationListAPIRequest(paasmaker.util.APIRequest):
	def __init__(self, *args, **kwargs):
		super(ApplicationListAPIRequest, self).__init__(*args, **kwargs)
		self.workspace_id = None
		self.method = 'GET'

	def set_workspace(self, workspace_id):
		self.workspace_id = workspace_id

	def get_endpoint(self):
		return '/workspace/%d/applications' % self.workspace_id
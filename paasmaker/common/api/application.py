
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

class ApplicationNewAPIRequest(paasmaker.util.APIRequest):
	def __init__(self, *args, **kwargs):
		self.params = {}
		self.params['manifest_path'] = 'manifest.yml'
		self.params['parameters'] = {}
		self.workspace_id = None
		super(ApplicationNewAPIRequest, self).__init__(*args, **kwargs)

	def set_workspace(self, workspace_id):
		self.workspace_id = workspace_id

	def set_uploaded_file(self, unique_identifier):
		self.params['uploaded_file'] = unique_identifier

	def set_scm(self, scm):
		self.params['scm'] = scm

	def set_parameters(self, parameters):
		self.params['parameters'] = parameters

	def set_manifest_path(self, manifest_path):
		self.params['manifest_path'] = manifest_path

	def build_payload(self):
		return self.params

	def get_endpoint(self):
		return '/workspace/%d/applications/new' % self.workspace_id

class ApplicationNewVersionAPIRequest(paasmaker.util.APIRequest):
	def __init__(self, *args, **kwargs):
		self.params = {}
		self.params['manifest_path'] = 'manifest.yml'
		self.params['parameters'] = {}
		self.application_id = None
		super(ApplicationNewVersionAPIRequest, self).__init__(*args, **kwargs)

	def set_application(self, application_id):
		self.application_id = application_id

	def set_uploaded_file(self, unique_identifier):
		self.params['uploaded_file'] = unique_identifier

	def set_scm(self, scm):
		self.params['scm'] = scm

	def set_parameters(self, parameters):
		self.params['parameters'] = parameters

	def set_manifest_path(self, manifest_path):
		self.params['manifest_path'] = manifest_path

	def build_payload(self):
		return self.params

	def get_endpoint(self):
		return '/application/%d/newversion' % self.application_id
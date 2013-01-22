
import logging

import paasmaker
from apirequest import APIRequest, APIResponse

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

class ApplicationGetAPIRequest(APIRequest):
	"""
	Get the details for a single application.
	"""

	def __init__(self, *args, **kwargs):
		super(ApplicationGetAPIRequest, self).__init__(*args, **kwargs)
		self.application_id = None
		self.method = 'GET'

	def set_application(self, application_id):
		"""
		Set the application ID for the request.
		"""
		self.application_id = application_id

	def get_endpoint(self):
		return '/application/%d' % self.application_id

class ApplicationListAPIRequest(APIRequest):
	"""
	List applications in a workspace.
	"""
	def __init__(self, *args, **kwargs):
		super(ApplicationListAPIRequest, self).__init__(*args, **kwargs)
		self.workspace_id = None
		self.method = 'GET'

	def set_workspace(self, workspace_id):
		"""
		Set the workspace ID to list the applications for.
		"""
		self.workspace_id = workspace_id

	def get_endpoint(self):
		return '/workspace/%d/applications' % self.workspace_id

class ApplicationNewAPIRequest(APIRequest):
	"""
	Create a new application.
	"""
	def __init__(self, *args, **kwargs):
		self.params = {}
		self.params['manifest_path'] = 'manifest.yml'
		self.params['parameters'] = {}
		self.workspace_id = None
		super(ApplicationNewAPIRequest, self).__init__(*args, **kwargs)

	def set_workspace(self, workspace_id):
		"""
		Set the workspace that this application belongs in.
		"""
		self.workspace_id = workspace_id

	def set_uploaded_file(self, unique_identifier):
		"""
		If the source for this new version is an uploaded file,
		this function sets the unique server-generated file
		identifier for this version.
		"""
		self.params['uploaded_file'] = unique_identifier

	def set_scm(self, scm):
		"""
		Set the SCM name for this new version.
		"""
		self.params['scm'] = scm

	def set_parameters(self, parameters):
		"""
		Set the SCM parameters for this new version.
		"""
		self.params['parameters'] = parameters

	def set_manifest_path(self, manifest_path):
		"""
		Set the manifest path inside the files. Defaults to ``manifest.yml``.
		"""
		self.params['manifest_path'] = manifest_path

	def build_payload(self):
		return self.params

	def get_endpoint(self):
		return '/workspace/%d/applications/new' % self.workspace_id

class ApplicationNewVersionAPIRequest(APIRequest):
	"""
	Create a new version of an existing application.
	"""
	def __init__(self, *args, **kwargs):
		self.params = {}
		self.params['manifest_path'] = 'manifest.yml'
		self.params['parameters'] = {}
		self.application_id = None
		super(ApplicationNewVersionAPIRequest, self).__init__(*args, **kwargs)

	def set_application(self, application_id):
		"""
		Set the application ID to create a new version for.
		"""
		self.application_id = application_id

	def set_uploaded_file(self, unique_identifier):
		"""
		If the source for this new version is an uploaded file,
		this function sets the unique server-generated file
		identifier for this version.
		"""
		self.params['uploaded_file'] = unique_identifier

	def set_scm(self, scm):
		"""
		Set the SCM name for this new version.
		"""
		self.params['scm'] = scm

	def set_parameters(self, parameters):
		"""
		Set the SCM parameters for this new version.
		"""
		self.params['parameters'] = parameters

	def set_manifest_path(self, manifest_path):
		"""
		Set the manifest path inside the files. Defaults to ``manifest.yml``.
		"""
		self.params['manifest_path'] = manifest_path

	def build_payload(self):
		return self.params

	def get_endpoint(self):
		return '/application/%d/newversion' % self.application_id

class ApplicationDeleteAPIRequest(APIRequest):
	"""
	Deletes an application.
	"""

	def __init__(self, *args, **kwargs):
		super(ApplicationDeleteAPIRequest, self).__init__(*args, **kwargs)
		self.application_id = None

	def set_application(self, application_id):
		"""
		Set the application ID for the request.
		"""
		self.application_id = application_id

	def get_endpoint(self):
		return '/application/%d/delete' % self.application_id

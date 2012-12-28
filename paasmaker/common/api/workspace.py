
import logging

import paasmaker
from apirequest import APIRequest, APIResponse

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

class WorkspaceGetAPIRequest(APIRequest):
	"""
	Get the details on a workspace.
	"""
	def __init__(self, *args, **kwargs):
		super(WorkspaceGetAPIRequest, self).__init__(*args, **kwargs)
		self.workspace_id = None
		self.method = 'GET'

	def set_workspace(self, workspace_id):
		"""
		Set the workspace ID to fetch.

		:arg int workspace_id: The workspace ID to fetch.
		"""
		self.workspace_id = workspace_id

	def get_endpoint(self):
		return '/workspace/%d' % self.workspace_id

class WorkspaceCreateAPIRequest(APIRequest):
	"""
	Create a new workspace. The name of the workspace and it's stub
	must be unique.
	"""
	def __init__(self, *args, **kwargs):
		self.params = {}
		super(WorkspaceCreateAPIRequest, self).__init__(*args, **kwargs)

	def set_workspace_name(self, name):
		"""
		Set the name of the workspace.

		:arg str name: The name of the workspace.
		"""
		self.params['name'] = name

	def set_workspace_tags(self, tags):
		"""
		Set the workspace's tags.

		:arg dict tags: A dict containing the tags. All tags
			should be directly JSON serializable.
		"""
		self.params['tags'] = tags

	def set_workspace_stub(self, stub):
		"""
		Set the workspace's stub - a name that can be placed
		directly into the hostname.

		:arg str stub: The stub for the workspace.
		"""
		self.params['stub'] = stub

	def build_payload(self):
		return self.params

	def get_endpoint(self):
		return '/workspace/create'

class WorkspaceEditAPIRequest(WorkspaceCreateAPIRequest):
	"""
	Edit an existing workspace. This class is a subclass
	of WorkspaceCreateAPIRequest, so you can use the mutators
	on that class to modify the workspace.
	"""
	def __init__(self, *args, **kwargs):
		super(WorkspaceEditAPIRequest, self).__init__(*args, **kwargs)
		self.workspace_id = None

	def set_workspace(self, workspace_id):
		"""
		Set the workspace ID to edit.

		:arg int workspace_id: The workspace ID to edit.
		"""
		self.workspace_id = workspace_id

	def load(self, workspace_id, callback, error_callback):
		"""
		Load the workspace from the server, calling the callback
		with data from the workspace. The data is also stored
		inside the class, ready to be mutated and sent
		back to the server.

		As this is a subclass of WorkspaceCreateAPIRequest, you can
		use the mutators on that class to modify the workspace.

		:arg int workspace_id: The workspace ID to load.
		:arg callable callback: The callback to call on success.
		:arg callable error_callback: The error callback on failure.
		"""
		request = WorkspaceGetAPIRequest(self.configuration)
		request.duplicate_auth(self)
		request.set_workspace(workspace_id)
		def on_load_complete(response):
			logger.debug("Loading complete.")
			if response.success:
				self.params.update(response.data['workspace'])
				self.workspace_id = self.params['id']
				logger.debug("Loading complete for workspace %d", self.workspace_id)
				callback(response.data['workspace'])
			else:
				logger.debug("Loading failed for workspace.")
				error_callback(str(response.errors))
		request.send(on_load_complete)
		logger.debug("Awaiting results of load from the server.")

	def get_endpoint(self):
		return "/workspace/%d" % self.workspace_id

class WorkspaceListAPIRequest(APIRequest):
	"""
	List all workspaces on the system. Only workspaces
	that you have permission to view are returned.
	"""
	def __init__(self, *args, **kwargs):
		super(WorkspaceListAPIRequest, self).__init__(*args, **kwargs)
		self.method = 'GET'

	def get_endpoint(self):
		return '/workspace/list'
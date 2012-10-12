
import paasmaker
import logging

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

class WorkspaceGetAPIRequest(paasmaker.util.APIRequest):
	def __init__(self, *args, **kwargs):
		super(WorkspaceGetAPIRequest, self).__init__(*args, **kwargs)
		self.workspace_id = None

	def set_workspace(self, workspace_id):
		self.workspace_id = workspace_id

	def get_endpoint(self):
		return '/workspace/%d' % self.workspace_id

class WorkspaceCreateAPIRequest(paasmaker.util.APIRequest):
	def __init__(self, *args, **kwargs):
		self.params = {}
		super(WorkspaceCreateAPIRequest, self).__init__(*args, **kwargs)

	def set_workspace_name(self, name):
		self.params['name'] = name

	def build_payload(self):
		return self.params

	def get_endpoint(self):
		return '/workspace/create'

class WorkspaceEditAPIRequest(WorkspaceCreateAPIRequest):
	def __init__(self, *args, **kwargs):
		super(WorkspaceEditAPIRequest, self).__init__(*args, **kwargs)
		self.workspace_id = None

	def set_workspace(self, workspace_id):
		self.workspace_id = workspace_id

	def load(self, workspace_id, callback):
		request = WorkspaceGetAPIRequest(self.configuration, self.io_loop)
		request.set_workspace(workspace_id)
		def on_load_complete(response):
			logger.debug("Loading complete.")
			if response.success:
				self.params.update(response.data['workspace'])
				self.workspace_id = self.params['id']
				logger.debug("Loading complete for workspace %d", self.workspace_id)
				callback(response)
			else:
				logger.debug("Loading failed for workspace.")
				callback(response)
		request.send(on_load_complete)
		logger.debug("Awaiting results of load from the server.")

	def get_endpoint(self):
		return "/workspace/edit/%d" % self.workspace_id

class WorkspaceListAPIRequest(paasmaker.util.APIRequest):
	def get_endpoint(self):
		return '/workspace/list'
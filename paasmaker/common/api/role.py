
import paasmaker
import logging

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

class RoleGetAPIRequest(paasmaker.util.APIRequest):
	def __init__(self, *args, **kwargs):
		super(RoleGetAPIRequest, self).__init__(*args, **kwargs)
		self.role_id = None
		self.method = 'GET'

	def set_role(self, role_id):
		self.role_id = role_id

	def get_endpoint(self):
		return '/role/%d' % self.role_id

class RoleCreateAPIRequest(paasmaker.util.APIRequest):
	def __init__(self, *args, **kwargs):
		self.params = {}
		super(RoleCreateAPIRequest, self).__init__(*args, **kwargs)

	def set_role_params(self, name, permissions):
		self.params['name'] = name
		self.params['permissions'] = permissions

	def set_role_name(self, name):
		self.params['name'] = name

	def set_role_permissions(self, permissions):
		self.params['permissions'] = permissions

	def build_payload(self):
		# Build our payload.
		payload = {}

		payload.update(self.params)
		return payload

	def get_endpoint(self):
		return '/role/create'

class RoleEditAPIRequest(RoleCreateAPIRequest):
	def __init__(self, *args, **kwargs):
		super(RoleEditAPIRequest, self).__init__(*args, **kwargs)
		self.role_id = None

	def set_role(self, role_id):
		self.role_id = role_id

	def load(self, role_id, callback, error_callback):
		request = RoleGetAPIRequest(self.configuration)
		request.duplicate_auth(self)
		request.set_role(role_id)
		def on_load_complete(response):
			logger.debug("Loading complete.")
			if response.success:
				self.params.update(response.data['role'])
				self.role_id = self.params['id']
				logger.debug("Loading complete for role %d", self.role_id)
				callback(response.data['role'])
			else:
				logger.debug("Loading failed for role.")
				error_callback(str(response.errors))
		request.send(on_load_complete)
		logger.debug("Awaiting results of load from the server.")

	def get_endpoint(self):
		return "/role/%d" % self.role_id

class RoleListAPIRequest(paasmaker.util.APIRequest):
	def __init__(self, *args, **kwargs):
		super(RoleListAPIRequest, self).__init__(*args, **kwargs)
		self.method = 'GET'

	def get_endpoint(self):
		return '/role/list'

class RoleAllocationListAPIRequest(paasmaker.util.APIRequest):
	def __init__(self, *args, **kwargs):
		super(RoleAllocationListAPIRequest, self).__init__(*args, **kwargs)
		self.method = 'GET'

	def get_endpoint(self):
		return '/role/allocation/list'

class RoleAllocationAPIRequest(paasmaker.util.APIRequest):
	def __init__(self, *args, **kwargs):
		self.params = {}
		super(RoleAllocationAPIRequest, self).__init__(*args, **kwargs)

	def set_allocation_params(self, user_id, role_id, workspace_id=None):
		self.params['user_id'] = user_id
		self.params['role_id'] = role_id
		if workspace_id:
			self.params['workspace_id'] = workspace_id

	def build_payload(self):
		# Build our payload.
		payload = {}
		payload.update(self.params)
		return payload

	def get_endpoint(self):
		return '/role/allocation/assign'

class RoleUnAllocationAPIRequest(paasmaker.util.APIRequest):
	def __init__(self, *args, **kwargs):
		self.params = {}
		super(RoleUnAllocationAPIRequest, self).__init__(*args, **kwargs)

	def set_allocation_id(self, allocation_id):
		self.params['allocation_id'] = allocation_id

	def build_payload(self):
		# Build our payload.
		payload = {}
		payload.update(self.params)
		return payload

	def get_endpoint(self):
		return '/role/allocation/unassign'
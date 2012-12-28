
import logging

import paasmaker
from apirequest import APIRequest, APIResponse

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

class RoleGetAPIRequest(APIRequest):
	"""
	Get the full information for a single role.
	"""
	def __init__(self, *args, **kwargs):
		super(RoleGetAPIRequest, self).__init__(*args, **kwargs)
		self.role_id = None
		self.method = 'GET'

	def set_role(self, role_id):
		"""
		Set the role ID to fetch.

		:arg int role_id: The role ID to fetch.
		"""
		self.role_id = role_id

	def get_endpoint(self):
		return '/role/%d' % self.role_id

class RoleCreateAPIRequest(APIRequest):
	"""
	Create a new role.
	"""
	def __init__(self, *args, **kwargs):
		self.params = {}
		super(RoleCreateAPIRequest, self).__init__(*args, **kwargs)

	def set_role_params(self, name, permissions):
		"""
		Set the parameters for the new role.

		:arg str name: The name for the role.
		:arg list permissions: A list of permissions to assign to
			the new role.
		"""
		self.params['name'] = name
		self.params['permissions'] = permissions

	def set_role_name(self, name):
		"""
		Set the name of the role.

		:arg str name: The name of the role.
		"""
		self.params['name'] = name

	def set_role_permissions(self, permissions):
		"""
		Set the permission on the role.

		:arg list permissions: A list of permissions to
			set for the role.
		"""
		self.params['permissions'] = permissions

	def build_payload(self):
		# Build our payload.
		payload = {}

		payload.update(self.params)
		return payload

	def get_endpoint(self):
		return '/role/create'

class RoleEditAPIRequest(RoleCreateAPIRequest):
	"""
	Edit an existing role. The role is loaded from the server,
	you set your changes, and the entire role is sent back to
	the server. If two simultaneous accesses occur, only the last
	will be recorded.
	"""
	def __init__(self, *args, **kwargs):
		super(RoleEditAPIRequest, self).__init__(*args, **kwargs)
		self.role_id = None

	def set_role(self, role_id):
		"""
		Set the role ID to edit.

		:arg int role_id: The role ID to edit.
		"""
		self.role_id = role_id

	def load(self, role_id, callback, error_callback):
		"""
		Load the role from the server, calling the callback
		with data from the role. The data is also stored
		inside the class, ready to be mutated and sent
		back to the server.

		As this is a subclass of RoleCreateAPIRequest, you can
		use the mutators on that class to modify the role.

		:arg int role_id: The role ID to load.
		:arg callable callback: The callback to call on success.
		:arg callable error_callback: The error callback on failure.
		"""
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

class RoleListAPIRequest(APIRequest):
	"""
	Get a list of roles from the server.
	"""
	def __init__(self, *args, **kwargs):
		super(RoleListAPIRequest, self).__init__(*args, **kwargs)
		self.method = 'GET'

	def get_endpoint(self):
		return '/role/list'

class RoleAllocationListAPIRequest(APIRequest):
	"""
	List role allocations from the server.
	"""
	def __init__(self, *args, **kwargs):
		super(RoleAllocationListAPIRequest, self).__init__(*args, **kwargs)
		self.method = 'GET'

	def get_endpoint(self):
		return '/role/allocation/list'

class RoleAllocationAPIRequest(APIRequest):
	"""
	Allocate a role to a user, and optionally to a workspace.
	"""
	def __init__(self, *args, **kwargs):
		self.params = {}
		super(RoleAllocationAPIRequest, self).__init__(*args, **kwargs)

	def set_allocation_params(self, user_id, role_id, workspace_id=None):
		"""
		Set the parameters for the allocation request to the server.

		:arg int user_id: The user ID to assign the role to.
		:arg int role_id: The role ID to assign.
		:arg int|None workspace_id: The optional workspace ID to assign
			the user and role to.
		"""
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

class RoleUnAllocationAPIRequest(APIRequest):
	"""
	Remove an existing role allocation from the server.
	"""
	def __init__(self, *args, **kwargs):
		self.params = {}
		super(RoleUnAllocationAPIRequest, self).__init__(*args, **kwargs)

	def set_allocation_id(self, allocation_id):
		"""
		Set the allocation ID to remove.

		:arg int allocation_id: The allocation ID to remove.
		"""
		self.params['allocation_id'] = allocation_id

	def build_payload(self):
		# Build our payload.
		payload = {}
		payload.update(self.params)
		return payload

	def get_endpoint(self):
		return '/role/allocation/unassign'
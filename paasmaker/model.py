import unittest
import json
import sqlalchemy
import datetime
import uuid
import paasmaker
from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Text, Enum, Table
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship, backref
from sqlalchemy.orm.interfaces import MapperExtension
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy import func
from sqlalchemy import or_
import hashlib

from paasmaker.common.core import constants

Base = declarative_base()

# TODO: Revisit this: DateTime handling: insert UTC timestamps.

# Helper function to return the time in UTC.
def now():
	return datetime.datetime.utcnow()

class OrmExtension(MapperExtension):
	def before_update(self, mapper, connection, instance):
		instance.updated = now()

class OrmBase(object):
	__mapper_args__ = { 'extension': OrmExtension() }
	created = Column(DateTime, nullable=False, default=now)
	deleted = Column(DateTime, nullable=True, default=None, index=True)
	updated = Column(DateTime, nullable=False, default=now)

	def flatten(self, field_list=None):
		# If field_list is not None, return just those fields.
		fields = {}
		if self.__dict__.has_key('id'):
			fields['id'] = self.__dict__['id']
			fields['updated'] = self.__dict__['updated']
			fields['created'] = self.__dict__['created']
		else:
			fields['id'] = None
			fields['updated'] = None
			fields['created'] = None
		fields['class'] = self.__class__.__name__
		for field in field_list:
			try:
				fields[field] = self.__dict__[field]
			except KeyError, ex:
				# Try again with the attribute getter, as it might be overriden.
				fields[field] = getattr(self, field)
		return fields

	def delete(self):
		"""Mark the object as deleted. You still need to save it."""
		self.deleted = now()

class Node(OrmBase, Base):
	__tablename__ = 'node'

	id = Column(Integer, primary_key=True)
	name = Column(String, nullable=False)
	route = Column(String, nullable=False)
	apiport = Column(Integer, nullable=False)
	uuid = Column(String, nullable=False, unique=True, index=True)
	state = Column(Enum(*constants.NODE.ALL), nullable=False)
	last_heard = Column(DateTime, nullable=False)

	heart = Column(Boolean, nullable=False, default=False)
	pacemaker = Column(Boolean, nullable=False, default=False)
	router = Column(Boolean, nullable=False, default=False)

	_tags = Column('tags', Text, nullable=False, default="{}")

	def __init__(self, name, route, apiport, uuid, state):
		self.name = name
		self.route = route
		self.apiport = apiport
		self.uuid = uuid
		self.state = state
		self.last_heard = datetime.datetime.utcnow()

	def __repr__(self):
		return "<Node('%s','%s')>" % (self.name, self.route)

	def flatten(self, field_list=None):
		return super(Node, self).flatten(['name', 'route', 'apiport', 'uuid', 'state', 'last_heard', 'heart', 'pacemaker', 'router', 'tags'])

	@hybrid_property
	def tags(self):
		if self._tags:
			return json.loads(self._tags)
		else:
			return {}

	@tags.setter
	def tags(self, val):
		self._tags = json.dumps(val)

class User(OrmBase, Base):
	__tablename__ = 'user'

	id = Column(Integer, primary_key=True)
	login = Column(String, nullable=False, index=True, unique=True)
	email = Column(String, nullable=False, index=True, unique=True)
	auth_source = Column(String, nullable=False, default="paasmaker.auth.internal")
	_auth_meta = Column("auth_meta", Text, nullable=True)
	enabled = Column(Boolean, nullable=False, default=True)

	_password = Column('password', String, nullable=True)
	name = Column(String, nullable=True)

	apikey = Column(String, nullable=True, index=True)

	def __init__(self):
		self.generate_api_key()

	def __repr__(self):
		return "<User('%s'@'%s')>" % (self.email, self.auth_source)

	@hybrid_property
	def password(self):
		return self._password
	@password.setter
	def password(self, val):
		self._password = self.password_hash(val)

	@hybrid_property
	def auth_meta(self):
		if self._auth_meta:
			return json.loads(self._auth_meta)
		else:
			return {}

	@auth_meta.setter
	def auth_meta(self, val):
		self._auth_meta = json.dumps(val)

	def flatten(self, field_list=None):
		return super(User, self).flatten(['login', 'email', 'auth_source', 'name', 'enabled'])

	def password_hash(self, plain):
		# Select a salt, if we don't already have one for this user.
		meta = self.auth_meta
		if not meta.has_key('salt'):
			meta['salt'] = str(uuid.uuid4())
		self.auth_meta = meta

		# Now hash their password, plus the salt.
		h = hashlib.md5()
		h.update(meta['salt'])
		h.update(plain)
		h.update(meta['salt'])
		return h.hexdigest()

	def generate_api_key(self):
		self.apikey = str(uuid.uuid4())

	def check_password(self, plain):
		return self.password == self.password_hash(plain)

class Role(OrmBase, Base):
	__tablename__ = 'role'

	id = Column(Integer, primary_key=True)
	name = Column(String, nullable=False, unique=True)
	_permissions = relationship("RolePermission", backref="role", cascade="all, delete, delete-orphan")

	def add_permission(self, name):
		if name not in self.permissions:
			new = RolePermission()
			new.role = self
			new.permission = name
			self._permissions.append(new)

	def remove_permission(self, name):
		# TODO: Is there a better way to do this?
		index = 0
		for perm in self.permissions:
			if perm == name:
				del self._permissions[index]
			index += 1

	def only_permissions(self, permissions):
		# TODO: Is there a better way to do this?
		for i in range(len(self._permissions) - 1, -1, -1):
			del self._permissions[i]
		for perm in permissions:
			self.add_permission(perm)

	@hybrid_property
	def permissions(self):
		perms = map(lambda x: x.permission, self._permissions)
		perms.sort()
		return perms

	@permissions.setter
	def permissions(self, val):
		if not isinstance(val, list):
			raise ValueError("Permissions must be a list of permissions.")
		self.only_permissions(val)

	def __repr__(self):
		return "<Role('%s' -> '%s')>" % (self.name, ",".join(self.permissions))

	def flatten(self, field_list=None):
		return super(Role, self).flatten(['name', 'permissions'])

class RolePermission(OrmBase, Base):
	__tablename__ = 'role_permission'

	id = Column(Integer, primary_key=True)
	role_id = Column(Integer, ForeignKey('role.id'), nullable=False, index=True)
	permission = Column(Enum(*constants.PERMISSION.ALL), nullable=False, index=True)

	def __repr__(self):
		return "<RolePermission('%s':'%s')>" % (self.role, self.permission)

	def flatten(self, field_list=None):
		return super(Node, self).flatten(['permission', 'role'])

class Workspace(OrmBase, Base):
	__tablename__ = 'workspace'

	id = Column(Integer, primary_key=True)
	name = Column(String, nullable=False, unique=True)
	_tags = Column('tags', Text, nullable=True)

	def __repr__(self):
		return "<Workspace('%s')>" % self.name

	def flatten(self, field_list=None):
		return super(Workspace, self).flatten(['name', 'tags'])

	@hybrid_property
	def tags(self):
		if self._tags:
			return json.loads(self._tags)
		else:
			return {}

	@tags.setter
	def tags(self, val):
		self._tags = json.dumps(val)

class WorkspaceUserRole(OrmBase, Base):
	__tablename__ = 'workspace_user_role'

	id = Column(Integer, primary_key=True)
	# workspace_id can be null, meaning it's global.
	workspace_id = Column(Integer, ForeignKey('workspace.id'), nullable=True, index=True)
	workspace = relationship("Workspace", backref=backref('users', order_by=id))
	role_id = Column(Integer, ForeignKey('role.id'), index=True)
	role = relationship("Role", backref=backref('workspaces', order_by=id))
	user_id = Column(Integer, ForeignKey('user.id'), index=True)
	user = relationship("User", backref=backref('workspaces', order_by=id))

	def __repr__(self):
		return "<WorkspaceUserRole('%s'@'%s' -> '%s')>" % (self.user, self.workspace, self.role)

	def flatten(self, field_list=None):
		return super(WorkspaceUserRole, self).flatten(['workspace', 'user', 'role'])

class WorkspaceUserRoleFlat(OrmBase, Base):
	__tablename__ = 'workspace_user_role_flat'

	# No backrefs here - this is primarily for lookup.
	id = Column(Integer, primary_key=True)
	# workspace_id can be null, meaning it's global.
	workspace_id = Column(Integer, ForeignKey('workspace.id'), nullable=True, index=True)
	workspace = relationship("Workspace")
	role_id = Column(Integer, ForeignKey('role.id'), index=True)
	role = relationship("Role")
	user_id = Column(Integer, ForeignKey('user.id'), index=True)
	user = relationship("User")
	permission = Column(Enum(*constants.PERMISSION.ALL), nullable=False, index=True)

	def __repr__(self):
		return "<WorkspaceUserRoleFlat('%s'@'%s' -> '%s')>" % (self.user, self.workspace, self.role)

	def flatten(self, field_list=None):
		return super(WorkspaceUserRoleFlat, self).flatten(['workspace', 'user', 'role'])

	@staticmethod
	def build_flat_table(session):
		session.query(WorkspaceUserRoleFlat).delete()
		links = session.query(WorkspaceUserRole)

		for link in links:
			for permission in link.role.permissions:
				# Create a new flat object for all of this data.
				flat = WorkspaceUserRoleFlat()
				# Workspace ID might be none.
				flat.workspace_id = link.workspace_id
				flat.user_id = link.user_id
				flat.role_id = link.role_id
				flat.permission = permission
				session.add(flat)

		session.commit()

	@staticmethod
	def has_permission(session, user, permission, workspace=None):
		# Figure out if the user has permission to do something.
		# We can easily determine this via a count on the flat
		# table, by matching a few parameters.

		query = session.query(
			WorkspaceUserRoleFlat
		).filter(
			WorkspaceUserRoleFlat.user_id == user.id
		).filter(
			WorkspaceUserRoleFlat.permission == permission
		)

		if workspace:
			# Either we need this permission on the given workspace,
			# or a global permission that says yes.
			query = query.filter(
				or_(
					WorkspaceUserRoleFlat.workspace_id == workspace.id,
					WorkspaceUserRoleFlat.workspace_id == None
				)
			)
		else:
			# Only a global permission will do.
			query = query.filter(
				WorkspaceUserRoleFlat.workspace_id == None
			)

		#print
		#print
		#print "Testing for %s for user %s on workspace %s" % (permission, user, workspace)
		#for res in query.all():
		#	print str(res)

		count = query.count()

		return count > 0

class Application(OrmBase, Base):
	__tablename__ = 'application'

	id = Column(Integer, primary_key=True)
	workspace_id = Column(Integer, ForeignKey('workspace.id'), nullable=False, index=True)
	workspace = relationship("Workspace", backref=backref('applications', order_by=id))
	# Application names are globally unique.
	name = Column(String, unique=True)
	manifest_path = Column(String, nullable=True)

	def __repr__(self):
		return "<Application('%s')>" % self.name

	def flatten(self, field_list=None):
		return super(Node, self).flatten(['name', 'workspace'])

	def flatten_for_heart(self):
		fields = ['name']
		return super(Application, self).flatten(fields)

# Joining table between Application Version and services.
application_version_services = Table('application_version_service', Base.metadata,
     Column('application_version_id', Integer, ForeignKey('application_version.id')),
     Column('service_id', Integer, ForeignKey('service.id'))
)

class ApplicationVersion(OrmBase, Base):
	__tablename__ = 'application_version'

	id = Column(Integer, primary_key=True)
	application_id = Column(Integer, ForeignKey('application.id'), nullable=False, index=True)
	application = relationship("Application", backref=backref('versions', order_by=id))
	version = Column(Integer, nullable=False)
	is_current = Column(Boolean, nullable=False)
	statistics = Column(Text, nullable=True)
	manifest = Column(Text, nullable=False)
	source_path = Column(String, nullable=True)
	source_checksum = Column(String, nullable=True)

	services = relationship('Service', secondary=application_version_services, backref='application_versions')

	def __init__(self):
		self.is_current = False

	def __repr__(self):
		return "<ApplicationVersion('%s'@'%s' - active: %s)>" % (self.version, self.application, str(self.is_current))

	def flatten(self, field_list=None):
		return super(ApplicationVersion, self).flatten(['application', 'version', 'is_current'])

	def flatten_for_heart(self):
		fields = ['version', 'source_path', 'source_checksum']
		return super(ApplicationVersion, self).flatten(fields)

	@staticmethod
	def get_next_version_number(session, application):
		query = session.query(func.max(ApplicationVersion.version)).filter_by(application=application)
		value = query[0][0]
		if value:
			return value + 1
		else:
			return 1

	def get_service_credentials(self):
		credentials = {}
		for service in self.services:
			credentials[service.name] = service.credentials

		return credentials

	def make_current(self, session):
		# Disable all versions.
		session.query(ApplicationVersion).filter(
			ApplicationVersion.application == self.application
		).update(
			{
				'is_current': False
			}
		)
		# And allow ours to be current. Commit it all in one transaction.
		self.is_current = True
		session.add(self)
		session.commit()

class ApplicationInstanceType(OrmBase, Base):
	__tablename__ = 'application_instance_type'

	id = Column(Integer, primary_key=True)
	application_version_id = Column(Integer, ForeignKey('application_version.id'), nullable=False, index=True)
	application_version = relationship("ApplicationVersion", backref=backref('instance_types', order_by=id))
	name = Column(String, nullable=False, index=True)
	quantity = Column(Integer, nullable=False)
	runtime_name = Column(Text, nullable=False)
	_runtime_parameters = Column("runtime_parameters", Text, nullable=False)
	runtime_version = Column(Text, nullable=False)
	_startup = Column("startup", Text, nullable=False)
	placement_provider = Column(Text, nullable=False)
	_placement_parameters = Column("placement_parameters", Text, nullable=False)
	exclusive = Column(Boolean, nullable=False)
	standalone = Column(Boolean, nullable=False)

	state = Column(Enum(*constants.INSTANCE_TYPE.ALL), nullable=False, index=True)

	def __repr__(self):
		return "<ApplicationInstanceType('%s'@'%s')>" % (self.name, self.runtime)

	def flatten(self, field_list=None):
		return super(ApplicationInstanceType, self).flatten(['name', 'application_version', 'quantity', 'provider'])

	def flatten_for_heart(self):
		fields = ['name', 'runtime_name', 'runtime_parameters', 'runtime_version', 'startup', 'exclusive', 'standalone']
		return super(ApplicationInstanceType, self).flatten(fields)

	@hybrid_property
	def placement_parameters(self):
		if self._placement_parameters:
			return json.loads(self._placement_parameters)
		else:
			return {}

	@placement_parameters.setter
	def placement_parameters(self, val):
		self._placement_parameters = json.dumps(val)

	@hybrid_property
	def runtime_parameters(self):
		if self._runtime_parameters:
			return json.loads(self._runtime_parameters)
		else:
			return {}

	@runtime_parameters.setter
	def runtime_parameters(self, val):
		self._runtime_parameters = json.dumps(val)

	@hybrid_property
	def startup(self):
		if self._startup:
			return json.loads(self._startup)
		else:
			return {}

	@startup.setter
	def startup(self, val):
		self._startup = json.dumps(val)

class ApplicationInstance(OrmBase, Base):
	__tablename__ = 'application_instance'

	id = Column(Integer, primary_key=True)
	instance_id = Column(String, nullable=False, index=True)
	application_instance_type_id = Column(Integer, ForeignKey('application_instance_type.id'), nullable=False, index=True)
	application_instance_type = relationship("ApplicationInstanceType", backref=backref('instances', order_by=id))
	node_id = Column(Integer, ForeignKey('node.id'), nullable=False, index=True)
	node = relationship("Node", backref=backref('nodes', order_by=id))
	port = Column(Integer, nullable=True, index=True)
	state = Column(Enum(*constants.INSTANCE.ALL), nullable=False, index=True)
	_statistics = Column("statistics", Text, nullable=True)

	def __repr__(self):
		return "<ApplicationInstance('%s'@'%s' - %s)>" % (self.application_instance_type, self.node, self.state)

	def flatten(self, field_list=None):
		return super(Node, self).flatten(['application_instance_type', 'node', 'state', 'port'])

	def flatten_for_heart(self):
		data = {}
		fields = ['instance_id', 'state']
		data['instance'] = super(ApplicationInstance, self).flatten(fields)
		data['instance_type'] = self.application_instance_type.flatten_for_heart()
		data['application_version'] = self.application_instance_type.application_version.flatten_for_heart()
		data['application'] = self.application_instance_type.application_version.application.flatten_for_heart()
		data['environment'] = paasmaker.common.application.environment.ApplicationEnvironment.get_instance_environment(self.application_instance_type.application_version)
		return data

	@hybrid_property
	def statistics(self):
		if self._statistics:
			return json.loads(self._statistics)
		else:
			return {}

	@statistics.setter
	def statistics(self, val):
		self._statistics = json.dumps(val)

class ApplicationInstanceTypeHostname(OrmBase, Base):
	__tablename__ = 'application_instance_type_hostname'

	id = Column(Integer, primary_key=True)
	application_instance_type_id = Column(Integer, ForeignKey('application_instance_type.id'), nullable=False, index=True)
	application_instance_type = relationship("ApplicationInstanceType", backref=backref('hostnames', order_by=id))

	hostname = Column(String, nullable=False, index=True)
	statistics = Column(Text, nullable=True)

	def __repr__(self):
		return "<ApplicationInstanceTypeHostname('%s' -> '%s')>" % (self.hostname, self.application_version)

	def flatten(self, field_list=None):
		return super(Node, self).flatten(['application_instance_type', 'hostname'])

class Service(OrmBase, Base):
	__tablename__ = 'service'

	id = Column(Integer, primary_key=True)
	workspace_id = Column(Integer, ForeignKey('workspace.id'), nullable=False, index=True)
	workspace = relationship("Workspace", backref=backref('workspace', order_by=id))
	name = Column(String, nullable=False, index=True, unique=True) # TODO: Unique per workspace.
	provider = Column(String, nullable=False, index=True)
	_parameters = Column('parameters', Text, nullable=False)
	_credentials = Column('credentials', Text, nullable=True)
	state = Column(Enum(*constants.SERVICE.ALL), nullable=False, index=True)

	@hybrid_property
	def parameters(self):
		return json.loads(self._parameters)
	@parameters.setter
	def parameters(self, val):
		self._parameters = json.dumps(val)
	@hybrid_property
	def credentials(self):
		if not self._credentials:
			return None
		else:
			return json.loads(self._credentials)
	@credentials.setter
	def credentials(self, val):
		self._credentials = json.dumps(val)

	def __repr__(self):
		return "<Service('%s'->'%s')>" % (self.provider, self.workspace)

	def flatten(self, field_list=None):
		return super(Node, self).flatten(['workspace', 'provider', 'credentials'])

	@staticmethod
	def get_or_create(session, workspace, name):
		# Find an existing one.
		service = session.query(Service).filter(Service.workspace == workspace, Service.name == name).first()
		if service:
			return service
		else:
			service = Service()
			service.workspace = workspace
			service.name = name
			service.state = constants.SERVICE.NEW
			return service

def init_db(engine):
	Base.metadata.create_all(bind=engine)

# From http://stackoverflow.com/questions/6941368/sqlalchemy-session-voes-in-unittest
# Thanks!
class TestModel(unittest.TestCase):
	def setUp(self):
		test_items = [
			Node(name='test', route='1.test.com', apiport=8888, uuid='1', state=constants.NODE.ACTIVE),
			Node(name='test2', route='2.test.com', apiport=8888, uuid='2', state=constants.NODE.ACTIVE)
		]

		engine = sqlalchemy.create_engine('sqlite:///:memory:', echo=False)
		DBSession = sessionmaker(bind=engine)
		self.session = DBSession()
		self.metadata = Base.metadata
		self.metadata.bind = engine
		self.metadata.drop_all() # Drop table
		self.metadata.create_all() # Create tables
		self.session.add_all(test_items) # Add data
		self.session.commit() # Commit

	def tearDown(self):
		self.session.close()

	def test_is_working(self):
		s = self.session
		item = s.query(Node).first()
		self.assertEquals(item.name, 'test', "Item has incorrect name.")
		self.assertIsNone(item.deleted, "Item does not have inherited attribute.")
		s.add(item)
		s.commit()
		self.assertEquals(item.id, 1, "Item is not id 1.")

	def test_created_timestamps(self):
		s = self.session
		n = Node('foo', 'bar', 8888, 'baz1', constants.NODE.ACTIVE)
		s.add(n)
		s.commit()
		n2 = Node('foo', 'bar', 8888, 'baz2', constants.NODE.ACTIVE)
		s.add(n2)
		s.commit()
		self.assertTrue(n2.created > n.created, "Created timestamp is not greater.")

	def test_updated_timestamp(self):
		s = self.session
		n = Node('foo', 'bar', 8888, 'baz3', constants.NODE.ACTIVE)
		s.add(n)
		s.commit()
		ts1 = str(n.updated)
		n.name = 'bar'
		s.add(n)
		s.commit()
		ts2 = str(n.updated)
		self.assertEquals(cmp(ts1, ts2), -1, "Updated timestamp did not change.")

	def test_user_workspace(self):
		s = self.session

		user = User()
		user.login = 'username'
		user.email = 'username@example.com'
		user.password = 'test'
		role = Role()
		role.name = 'Administrator'
		role.add_permission(constants.PERMISSION.USER_CREATE)

		s.add(user)
		s.add(role)

		s.commit()

		# TODO: APIkey isn't set until the password is set.
		# Fix this.
		s.refresh(user)
		self.assertTrue(user.apikey)

		workspace = Workspace()
		workspace.name = 'Work Zone'
		workspace.tags = {'test': 'tag'}
		s.add(workspace)
		s.commit()

		wu = WorkspaceUserRole()
		wu.workspace = workspace
		wu.role = role
		wu.user = user
		s.add(wu)
		s.commit()

		self.assertEquals(len(workspace.users), 1, "Workspace does not have a user.")
		self.assertEquals(len(workspace.tags.keys()), 1, "Workspace tags is not correct.")
		self.assertEquals(len(role.workspaces), 1, "Role does not have a workspace.")
		self.assertEquals(len(role.permissions), 1, "Role does not have any permissions.")

	def test_flatten(self):
		s = self.session
		item = s.query(Node).first()
		flat = item.flatten()
		self.assertEquals(len(flat.keys()), 14, "Item has incorrect number of keys.")
		self.assertTrue(flat.has_key('id'), "Missing ID.")
		self.assertTrue(flat.has_key('name'), "Missing name.")
		self.assertTrue(isinstance(flat['id'], int), "ID is not an integer.")

		data = { 'node': item }
		encoded = json.dumps(data, cls=paasmaker.util.jsonencoder.JsonEncoder)
		decoded = json.loads(encoded)

		self.assertEquals(decoded['node']['id'], 1, "ID is not correct.")

	def test_user_permissions(self):
		s = self.session

		user = User()
		user.login = 'username'
		user.email = 'username@example.com'
		user.password = 'test'
		role = Role()
		role.name = 'Workspace Level'
		role.add_permission(constants.PERMISSION.WORKSPACE_VIEW)

		s.add(user)
		s.add(role)

		s.commit()

		workspace = Workspace()
		workspace.name = 'Work Zone'
		workspace.tags = {'test': 'tag'}
		s.add(workspace)
		s.commit()

		wu = WorkspaceUserRole()
		wu.workspace = workspace
		wu.user = user
		wu.role = role
		s.add(wu)
		s.commit()

		# Rebuild the permissions table.
		WorkspaceUserRoleFlat.build_flat_table(s)

		# Do some basic tests.
		has_permission = WorkspaceUserRoleFlat.has_permission(
			s,
			user,
			constants.PERMISSION.WORKSPACE_VIEW,
			workspace
		)
		self.assertTrue(has_permission, "Unable to view workspace.")
		has_permission = WorkspaceUserRoleFlat.has_permission(
			s,
			user,
			constants.PERMISSION.WORKSPACE_CREATE,
			workspace
		)
		self.assertFalse(has_permission, "Can create workspace.")
		has_permission = WorkspaceUserRoleFlat.has_permission(
			s,
			user,
			constants.PERMISSION.WORKSPACE_VIEW,
			None
		)
		self.assertFalse(has_permission, "Can view workspace on global level.")
		has_permission = WorkspaceUserRoleFlat.has_permission(
			s,
			user,
			constants.PERMISSION.WORKSPACE_CREATE,
			None
		)
		self.assertFalse(has_permission, "Can create workspace.")

		# Revoke permission, then try again.
		role.remove_permission(constants.PERMISSION.WORKSPACE_VIEW)
		s.add(role)
		s.commit()
		WorkspaceUserRoleFlat.build_flat_table(s)

		has_permission = WorkspaceUserRoleFlat.has_permission(
			s,
			user,
			constants.PERMISSION.WORKSPACE_VIEW,
			workspace
		)
		self.assertFalse(has_permission, "Can view workspace.")
		has_permission = WorkspaceUserRoleFlat.has_permission(
			s,
			user,
			constants.PERMISSION.WORKSPACE_VIEW,
			None
		)
		self.assertFalse(has_permission, "Can view workspace on global level.")

		# Now set the permissions using the array whole set method.
		role.permissions = [constants.PERMISSION.WORKSPACE_VIEW]
		s.add(role)
		s.commit()
		WorkspaceUserRoleFlat.build_flat_table(s)

		has_permission = WorkspaceUserRoleFlat.has_permission(
			s,
			user,
			constants.PERMISSION.WORKSPACE_VIEW,
			workspace
		)
		self.assertTrue(has_permission, "Can't view workspace.")

		# Now assign a global permission.
		role_global = Role()
		role_global.name = 'Global Level'
		role_global.add_permission(constants.PERMISSION.USER_CREATE)

		s.add(role_global)

		wuglobal = WorkspaceUserRole()
		wuglobal.user = user
		wuglobal.role = role_global
		s.add(wuglobal)
		s.commit()

		# Rebuild the permissions table.
		WorkspaceUserRoleFlat.build_flat_table(s)

		has_permission = WorkspaceUserRoleFlat.has_permission(
			s,
			user,
			constants.PERMISSION.USER_CREATE,
			workspace
		)
		self.assertTrue(has_permission, "Can't create user.")
		has_permission = WorkspaceUserRoleFlat.has_permission(
			s,
			user,
			constants.PERMISSION.USER_CREATE,
			None
		)
		self.assertTrue(has_permission, "Can't create user.")

		user_two = User()
		user_two.login = 'username_two'
		user_two.email = 'username_two@example.com'
		user_two.password = 'test'
		s.add(user_two)
		s.commit()

		# Rebuild the permissions table.
		WorkspaceUserRoleFlat.build_flat_table(s)

		# And make sure that new user can't do anything.
		has_permission = WorkspaceUserRoleFlat.has_permission(
			s,
			user_two,
			constants.PERMISSION.USER_CREATE,
			workspace
		)
		self.assertFalse(has_permission, "Can create user.")
		has_permission = WorkspaceUserRoleFlat.has_permission(
			s,
			user_two,
			constants.PERMISSION.USER_CREATE,
			None
		)
		self.assertFalse(has_permission, "Can create user.")

		# TODO: Think of more imaginitive ways that this
		# very very simple permissions system can be broken,
		# and test them.
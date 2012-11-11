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
		data = super(Node, self).flatten(['name', 'route', 'apiport', 'uuid', 'state', 'last_heard', 'heart', 'pacemaker', 'router', 'tags'])
		return data

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

	def __init__(self, name):
		self.name = name

	def __repr__(self):
		return "<Role('%s')>" % self.name

	def flatten(self, field_list=None):
		return super(Node, self).flatten(['name', 'permissions'])

class RolePermission(OrmBase, Base):
	__tablename__ = 'role_permission'

	id = Column(Integer, primary_key=True)
	role_id = Column(Integer, ForeignKey('role.id'), nullable=False, index=True)
	role = relationship("Role", backref=backref('permissions', order_by=id))
	name = Column(String, nullable=False, index=True)
	granted = Column(Boolean, nullable=False, index=True)

	role = relationship("Role", backref=backref('permissions', order_by=id))

	def __init__(self, name, granted):
		self.name = name
		self.granted = granted

	def __repr__(self):
		return "<RolePermission('%s' -> '%s')>" % (self.name, str(self.granted))

	def flatten(self, field_list=None):
		return super(Node, self).flatten(['name', 'role', 'granted'])

class Workspace(OrmBase, Base):
	__tablename__ = 'workspace'

	id = Column(Integer, primary_key=True)
	name = Column(String, nullable=False, unique=True)
	_tags = Column('tags', Text, nullable=True)

	def __init__(self):
		pass

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

class WorkspaceUser(OrmBase, Base):
	__tablename__ = 'workspace_user'

	id = Column(Integer, primary_key=True)
	workspace_id = Column(Integer, ForeignKey('workspace.id'), nullable=False, index=True)
	workspace = relationship("Workspace", backref=backref('users', order_by=id))
	role_id = Column(Integer, ForeignKey('role.id'), index=True)
	role = relationship("Role", backref=backref('workspaces', order_by=id))
	user_id = Column(Integer, ForeignKey('user.id'), index=True)
	user = relationship("User", backref=backref('workspaces', order_by=id))

	def __init__(self, workspace, role, user):
		self.workspace = workspace
		self.role = role
		self.user = user

	def __repr__(self):
		return "<WorkspaceUser('%s'@'%s' -> '%s')>" % (self.user, self.workspace, self.role)

	def flatten(self, field_list=None):
		return super(Node, self).flatten(['workspace', 'user', 'role'])

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

class Job(OrmBase, Base):
	__tablename__ = 'job'

	id = Column(Integer, primary_key=True)
	unique = Column(String, nullable=False, index=True)
	title = Column(String, nullable=False)
	summary = Column(String, nullable=True)

	# This can refer to itself. The parent job should theoretically only
	# succeed when all the child jobs succeed.
	parent_id = Column(Integer, ForeignKey('job.id'), nullable=True)
	children = relationship("Job")

	state = Column(Enum(*constants.JOB.ALL), nullable=False, index=True)

	def __repr__(self):
		return "<Job('%s':'%s')>" % (self.unique, self.title)

	def flatten(self, field_list=None):
		return super(Node, self).flatten(['unique', 'title', 'summary', 'state'])

def init_db(engine):
	Base.metadata.create_all(bind=engine)

# From http://stackoverflow.com/questions/6941368/sqlalchemy-session-voes-in-unittest
# Thanks!
class TestModel(unittest.TestCase):
	is_setup = False
	session = None
	metadata = None

	test_items = [
		Node(name='test', route='1.test.com', apiport=8888, uuid='1', state=constants.NODE.ACTIVE),
		Node(name='test2', route='2.test.com', apiport=8888, uuid='2', state=constants.NODE.ACTIVE)
	]

	def setUp(self):
		if not self.__class__.is_setup:
			engine = sqlalchemy.create_engine('sqlite:///:memory:', echo=False)
			DBSession = sessionmaker(bind=engine)
			self.__class__.session = DBSession()
			self.metadata = Base.metadata
			self.metadata.bind = engine
			self.metadata.drop_all() # Drop table
			self.metadata.create_all() # Create tables
			self.__class__.session.add_all(self.test_items) # Add data
			self.__class__.session.commit() # Commit
			self.__class__.is_setup = True

	def tearDown(self):
		if self.__class__.is_setup:
			self.__class__.session.close()

	def test_is_working(self):
		s = self.__class__.session
		item = s.query(Node).first()
		self.assertEquals(item.name, 'test', "Item has incorrect name.")
		self.assertIsNone(item.deleted, "Item does not have inherited attribute.")
		s.add(item)
		s.commit()
		self.assertEquals(item.id, 1, "Item is not id 1.")

	def test_created_timestamps(self):
		s = self.__class__.session
		n = Node('foo', 'bar', 8888, 'baz1', constants.NODE.ACTIVE)
		s.add(n)
		s.commit()
		n2 = Node('foo', 'bar', 8888, 'baz2', constants.NODE.ACTIVE)
		s.add(n2)
		s.commit()
		self.assertTrue(n2.created > n.created, "Created timestamp is not greater.")

	def test_updated_timestamp(self):
		s = self.__class__.session
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
		s = self.__class__.session

		user = User()
		user.login = 'username'
		user.email = 'username@example.com'
		user.password = 'test'
		role = Role('Administrator')
		role_permission = RolePermission('ADMIN', True)
		role.permissions.append(role_permission)

		s.add(user)
		s.add(role)
		s.add(role_permission)

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

		wu = WorkspaceUser(workspace, role, user)
		s.add(wu)
		s.commit()

		self.assertEquals(len(workspace.users), 1, "Workspace does not have a user.")
		self.assertEquals(len(workspace.tags.keys()), 1, "Workspace tags is not correct.")
		self.assertEquals(len(role.workspaces), 1, "Role does not have a workspace.")
		self.assertEquals(len(role.permissions), 1, "Role does not have any permissions.")

	def test_flatten(self):
		s = self.__class__.session
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

	@classmethod
	def setUpClass(cls):
		pass

	@classmethod
	def tearDownClass(cls):
		pass

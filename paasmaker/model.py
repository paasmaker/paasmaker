#!/usr/bin/env python

import unittest
import sqlalchemy
import datetime
from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship, backref
from sqlalchemy.orm.interfaces import MapperExtension

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
	deleted = Column(DateTime, nullable=True, default=None)
	updated = Column(DateTime, nullable=False, default=now)

	def flatten(self, field_list=None):
		# If field_list is not None, return just those fields.
		fields = {}
		fields['id'] = self.__dict__['id']
		fields['updated'] = self.__dict__['updated']
		fields['created'] = self.__dict__['created']
		for field in field_list:
			fields[field] = self.__dict__[field]
		return fields

	def delete(self):
		"""Mark the object as deleted. You still need to save it."""
		self.deleted = now()

class Node(OrmBase, Base):
	__tablename__ = 'node'

	id = Column(Integer, primary_key=True)
	name = Column(String, nullable=False)
	route = Column(String, nullable=False)
	uuid = Column(String, nullable=False, unique=True)
	state = Column(String, nullable=False)
	last_heard = Column(DateTime)

	def __init__(self, name, route, uuid, state):
		self.name = name
		self.route = route
		self.uuid = uuid
		self.state = state
		self.last_heard = datetime.datetime.utcnow()

	def __repr__(self):
		return "<Node('%s','%s')>" % (self.name, self.route)

	def flatten(self, field_list=None):
		return OrmBase.flatten(self, ['name', 'route', 'uuid', 'state', 'last_heard'])		

class User(OrmBase, Base):
	__tablename__ = 'user'

	id = Column(Integer, primary_key=True)
	username = Column(String, nullable=False)
	auth_source = Column(String, nullable=False, default="internal")
	auth_meta = Column(String, nullable=True)

	password = Column(String, nullable=True)
	name = Column(String, nullable=True)

	def __init__(self, username, auth_source="internal"):
		self.username = username
		self.auth_source = auth_source

	def __repr__(self):
		return "<User('%s'@'%s')>" % (self.username, self.auth_source)

class Role(OrmBase, Base):
	__tablename__ = 'role'

	id = Column(Integer, primary_key=True)
	name = Column(String, nullable=False, unique=True)

	def __init__(self, name):
		self.name = name

	def __repr__(self):
		return "<Role('%s')>" % self.name

class RolePermission(OrmBase, Base):
	__tablename__ = 'role_permission'

	id = Column(Integer, primary_key=True)
	role_id = Column(Integer, ForeignKey('role.id'), nullable=False)
	name = Column(String, nullable=False)
	granted = Column(Boolean, nullable=False)

	role = relationship("Role", backref=backref('permissions', order_by=id))

	def __init__(self, name, granted):
		self.name = name
		self.granted = granted

	def __repr__(self):
		return "<RolePermission('%s' -> '%s')>" % (self.name, str(self.granted))

class Workspace(OrmBase, Base):
	__tablename__ = 'workspace'

	id = Column(Integer, primary_key=True)
	name = Column(String, nullable=False, unique=True)

	def __init__(self, name):
		self.name = name
	
	def __repr__(self):
		return "<Workspace('%s')>" % self.name

class WorkspaceUser(OrmBase, Base):
	__tablename__ = 'workspace_user'

	id = Column(Integer, primary_key=True)
	workspace_id = Column(Integer, ForeignKey('workspace.id'), nullable=False)
	workspace = relationship("Workspace", backref=backref('users', order_by=id))
	role_id = Column(Integer, ForeignKey('role.id'))
	role = relationship("Role", backref=backref('workspaces', order_by=id))
	user_id = Column(Integer, ForeignKey('user.id'))
	user = relationship("User", backref=backref('workspaces', order_by=id))

	def __init__(self, workspace, role, user):
		self.workspace = workspace
		self.role = role
		self.user = user

	def __repr__(self):
		return "<WorkspaceUser('%s'@'%s' -> '%s')>" % (self.user, self.workspace, self.role)

class Application(OrmBase, Base):
	__tablename__ = 'application'

	id = Column(Integer, primary_key=True)
	workspace_id = Column(Integer, ForeignKey('workspace.id'), nullable=False)
	workspace = relationship("Workspace", backref=backref('applications', order_by=id))
	# Application names are globally unique.
	name = Column(String, unique=True)

	def __init__(self, name, workspace):
		self.workspace = workspace
		self.name = name
	
	def __repr__(self):
		return "<Application('%s')>" % self.name

class ApplicationVersion(OrmBase, Base):
	__tablename__ = 'application_version'

	id = Column(Integer, primary_key=True)
	application_id = Column(Integer, ForeignKey('application.id'), nullable=False)
	application = relationship("Application", backref=backref('versions', order_by=id))
	version = Column(String, nullable=False)
	is_current = Column(Boolean, nullable=False)

	def __init__(self, application, version):
		self.application = application
		self.version = version
		self.is_current = False

	def __repr__(self):
		return "<ApplicationVersion('%s'@'%s' - active: %s)>" % (self.version, self.application, str(self.is_current))

class ApplicationInstance(OrmBase, Base):
	__tablename__ = 'application_instance'

	id = Column(Integer, primary_key=True)
	application_version_id = Column(Integer, ForeignKey('application_version.id'), nullable=False)
	application_version = relationship("ApplicationVersion", backref=backref('instances', order_by=id))
	node_id = Column(Integer, ForeignKey('node.id'), nullable=False)
	node = relationship("Node", backref=backref('nodes', order_by=id))
	status = Column(String, nullable=False)

	def __init__(self, application_version, node):
		self.application_version = application_version
		self.node = node
		self.status = status
	
	def __repr__(self):
		return "<ApplicationInstance('%s'@'%s' - %s)>" % (self.application_version, self.node, self.status)


def init_db(engine):
	Base.metadata.create_all(bind=engine)

# From http://stackoverflow.com/questions/6941368/sqlalchemy-session-voes-in-unittest
# Thanks!
class TestModel(unittest.TestCase):
	is_setup = False
	session = None
	metadata = None

	test_items = [
		Node(name='test', route='1.test.com', uuid='1', state='new'),
		Node(name='test2', route='2.test.com', uuid='2', state='new')
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
		n = Node('foo', 'bar', 'baz1', 'boo')
		s.add(n)
		s.commit()
		n2 = Node('foo', 'bar', 'baz2', 'boo')
		s.add(n2)
		s.commit()
		self.assertTrue(n2.created > n.created, "Created timestamp is not greater.")

	def test_updated_timestamp(self):
		s = self.__class__.session
		n = Node('foo', 'bar', 'baz3', 'boo')
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

		user = User('danielf')
		role = Role('Administrator')
		role_permission = RolePermission('ADMIN', True)
		role.permissions.append(role_permission)

		s.add(user)
		s.add(role)
		s.add(role_permission)

		s.commit()

		workspace = Workspace('Work Zone')
		s.add(workspace)
		s.commit()

		wu = WorkspaceUser(workspace, role, user)
		s.add(wu)
		s.commit()

		self.assertEquals(len(workspace.users), 1, "Workspace does not have a user.")
		self.assertEquals(len(role.workspaces), 1, "Role does not have a workspace.")
		self.assertEquals(len(role.permissions), 1, "Role does not have any permissions.")

	def test_flatten(self):
		s = self.__class__.session
		item = s.query(Node).first()
		flat = item.flatten()
		self.assertEquals(len(flat.keys()), 8, "Item is missing keys.")
		self.assertTrue(flat.has_key('id'), "Missing ID.")
		self.assertTrue(isinstance(flat['id'], int), "ID is not an integer.")

	@classmethod
	def setUpClass(cls):
		pass

	@classmethod
	def tearDownClass(cls):
		pass

if __name__ == '__main__':
	unittest.main()

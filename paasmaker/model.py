#
# Paasmaker - Platform as a Service
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#

import unittest
import json
import datetime
import uuid
import hashlib
import logging
import socket

import paasmaker
from paasmaker.common.core import constants

import sqlalchemy
from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Text, Table, Index, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship, backref
from sqlalchemy.orm.interfaces import MapperExtension
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy import func
from sqlalchemy import or_

from passlib.context import CryptContext

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

password_hashing_context = CryptContext(schemes=["sha512_crypt"])

Base = declarative_base()

# Helper function to return the time in UTC.
def now():
	return datetime.datetime.utcnow()

class OrmExtension(MapperExtension):
	def before_update(self, mapper, connection, instance):
		instance.updated = now()

class OrmBase(object):
	"""
	An ORM base class, that is the super class of all other
	ORM objects.

	Provides the following to all classes:

	* Automatic created, deleted, and updated fields, and handles
	  updating the updated field as appropriate.
	* Provides a ``flatten()`` method for each ORM class.
	* Provides a ``delete()`` helper method.
	"""
	__mapper_args__ = { 'extension': OrmExtension() }
	created = Column(DateTime, nullable=False, default=now)
	deleted = Column(DateTime, nullable=True, default=None, index=True)
	updated = Column(DateTime, nullable=False, default=now, index=True)

	def flatten(self, field_list=None):
		"""
		"Flatten" this ORM object into a dict, ready for
		JSON encoding.

		The idea is that not all fields should be returned. Some
		will be private, or have internal meanings and thus not
		required to be exposed externally.

		Your class should override this function, calling
		this function with a list of fields to return.

		If you return a field that references another ORM object,
		it will be flattened and returned as well. Be careful
		of this as it will then propagate upwards.

		The following additional fields are returned for each
		object:

		* The database ID.
		* The created and updated timestamps, in iso format.
		* An ``updated_age`` and ``created_age`` field, in seconds,
		  that is the time since the record was updated or created.
		* ``class`` - The name of the class that this record is
		  from.

		:arg list field_list: A list of fields to return in the
			dict. If no fields are given, only the ID and timestamps
			are returned.
		"""
		# If field_list is not None, return just those fields.
		fields = {}
		if self.__dict__.has_key('id') and self.__dict__['id']:
			fields['id'] = self.__dict__['id']
			fields['updated'] = self.__dict__['updated']
			fields['created'] = self.__dict__['created']

			# Calculate the age of the record.
			# Why use the same reference? So they're both relative
			# to exactly the same time.
			reference = now()
			fields['updated_age'] = self.updated_age(reference)
			fields['created_age'] = self.created_age(reference)
		else:
			fields['id'] = None
			fields['updated'] = None
			fields['updated_age'] = None
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
		"""
		Mark the object as deleted. You still need to save it for this
		to take effect.
		"""
		self.deleted = now()

	def updated_age(self, reference=None):
		"""
		Calculate the updated age, in seconds, of this object.

		If supplied with a reference date time, the age is
		calculated relative to that time.

		:arg datetime reference: The reference time to calculate
			against.
		"""
		if not reference:
			reference = now()
		return (reference - self.updated).total_seconds()

	def created_age(self, reference=None):
		"""
		Calculate the created age, in seconds, of this object.

		If supplied with a reference date time, the age is
		calculated relative to that time.

		:arg datetime reference: The reference time to calculate
			against.
		"""
		if not reference:
			reference = now()
		return (reference - self.created).total_seconds()

class Node(OrmBase, Base):
	"""
	Node - a node in the cluster.

	Special fields:

	* **tags**: takes a dict which is internally stored as
	  a JSON encoded string.
	"""
	__tablename__ = 'node'

	id = Column(Integer, primary_key=True)
	name = Column(String(255), nullable=False)
	route = Column(String(255), nullable=False)
	apiport = Column(Integer, nullable=False)
	uuid = Column(String(255), nullable=False, unique=True, index=True)
	state = Column(String(255), nullable=False, index=True)
	last_heard = Column(DateTime, nullable=False)
	start_time = Column(DateTime, nullable=False)

	heart = Column(Boolean, nullable=False, default=False)
	pacemaker = Column(Boolean, nullable=False, default=False)
	router = Column(Boolean, nullable=False, default=False)

	_tags = Column('tags', Text, nullable=False, default="{}")
	_stats = Column('stats', Text, nullable=False, default="{}")
	score = Column(Float, nullable=False, default=1.0, index=True)

	def __init__(self, name, route, apiport, uuid, state):
		self.name = name
		self.route = route
		self.apiport = apiport
		self.uuid = uuid
		self.state = state
		self.last_heard = datetime.datetime.utcnow()
		self.start_time = datetime.datetime.utcnow()

	def __repr__(self):
		return "<Node('%s','%s',%d)>" % (self.name, self.route, self.apiport)

	def flatten(self, field_list=None):
		return super(Node, self).flatten(['name', 'route', 'apiport', 'uuid', 'state', 'start_time', 'last_heard', 'heart', 'pacemaker', 'router', 'tags', 'score', 'stats', 'can_delete'])

	@hybrid_property
	def tags(self):
		if self._tags:
			return json.loads(self._tags)
		else:
			return {}

	@tags.setter
	def tags(self, val):
		self._tags = json.dumps(val)

	@hybrid_property
	def stats(self):
		if self._stats:
			return json.loads(self._stats)
		else:
			return {}

	@stats.setter
	def stats(self, val):
		self._stats = json.dumps(val)

	def uptime(self, reference=None):
		"""
		Calculate the uptime of this node object.

		If supplied with a reference date time, the uptime is
		calculated relative to that time.

		:arg datetime reference: The reference time to calculate
			against.
		"""
		if not reference:
			reference = now()
		return (reference - self.start_time).total_seconds()

	def get_pacemaker_location(self):
		"""
		Get the router location entry for this pacemaker
		instance. The location includes an IP address, and several
		keys that are used to account for the traffic.
		"""
		# TODO: Make this lookup async.
		# TODO: IPv6 support.
		# The format of the key is:
		# <address>:<port>#pacemaker#<node id>#null
		router_location = '%s:%d#pacemaker#%d#null' % (
			socket.gethostbyname(self.route),
			self.apiport,
			self.id
		)

		return router_location

	@property
	def can_delete(self):
		"""
		Nodes can only be deleted if they're in a stopped state.
		"""
		return self.state in constants.NODE_STOPPED_STATES

class User(OrmBase, Base):
	"""
	User - a user who can access the system.

	Special Fields:

	* **password**: When assigned, this is automatically hashed.
	  Each user has a custom salt that is stored in the auth_meta
	  dictionary.
	* **auth_meta**: This is a dictionary, stored JSON encoded
	  into a text field.
	"""
	__tablename__ = 'user'

	id = Column(Integer, primary_key=True)
	login = Column(String(255), nullable=False, index=True, unique=True)
	email = Column(String(255), nullable=False, index=True, unique=True)
	auth_source = Column(String(255), nullable=False, default="paasmaker.auth.internal")
	_auth_meta = Column("auth_meta", Text, nullable=True)
	enabled = Column(Boolean, nullable=False, default=True)

	_password = Column('password', String(255), nullable=True)
	name = Column(String(255), nullable=True)

	apikey = Column(String(255), nullable=True, index=True)

	_userdata = Column("userdata", Text, nullable=True)

	def __init__(self):
		self.generate_api_key()

	def __repr__(self):
		return "<User('%s'@'%s')>" % (self.email, self.auth_source)

	@hybrid_property
	def password(self):
		return self._password
	@password.setter
	def password(self, val):
		meta = self.auth_meta
		if 'hashlibrary' not in meta:
			# Upgrade old versions of Paasmaker once the password
			# is reset. This doesn't change libraries however.
			meta['hashlibrary'] = 'passlib'
			self.auth_meta = meta

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

	@hybrid_property
	def userdata(self):
		if self._userdata:
			return json.loads(self._userdata)
		else:
			return {}

	@userdata.setter
	def userdata(self, val):
		self._userdata = json.dumps(val)

	def flatten(self, field_list=None):
		return super(User, self).flatten(['login', 'email', 'auth_source', 'name', 'enabled'])

	def password_hash(self, plain):
		"""
		Hash a plain text password.

		:arg str plain: The plain text password.
		"""
		meta = self.auth_meta

		if 'hashlibrary' in meta:
			# Use that hash library.
			if meta['hashlibrary'] == 'passlib':
				# Access the single global context.
				return password_hashing_context.encrypt(plain)
			else:
				raise ValueError("Hashing library %s is unknown in this version." % meta['hashlibrary'])
		else:
			# Use the old fashioned and insecure md5+salt hashing.
			# Select a salt, if we don't already have one for this user.
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
		"""
		Generate an API key for the user.

		If the user already had an API key, this generates
		a new one.
		"""
		self.apikey = str(uuid.uuid4())

	def check_password(self, plain):
		"""
		Check the plain password to see if it matches the stored
		hash.

		:arg str plain: The plain text password.
		"""
		meta = self.auth_meta

		if 'hashlibrary' in meta:
			# Use that hash library.
			if meta['hashlibrary'] == 'passlib':
				# Access the single global context.
				return password_hashing_context.verify(plain, self.password)
			else:
				raise ValueError("Hashing library %s is unknown in this version." % meta['hashlibrary'])
		else:
			return self.password == self.password_hash(plain)

class Role(OrmBase, Base):
	"""
	Role - a named set of permissions that a user might assume.

	Special Fields:

	* **permissions**: a relationship to the RolePermission class.
	  Note that this class takes over handling all of the attached
	  permission objects via it's methods - you should not manage
	  these separately yourself.
	"""
	__tablename__ = 'role'

	id = Column(Integer, primary_key=True)
	name = Column(String(255), nullable=False, unique=True)
	_permissions = relationship("RolePermission", backref="role", cascade="all, delete, delete-orphan")

	def add_permission(self, name):
		"""
		Add a specific permission to this role.

		You still need to save the object after calling
		this.

		:arg str name: The permission name to add.
		"""
		if name not in self.permissions:
			new = RolePermission()
			new.role = self
			new.permission = name
			self._permissions.append(new)

	def remove_permission(self, name):
		"""
		Remove a specific permission from this role.

		You still need to save the object after calling this.

		:arg str name: The permission name to remove.
		"""
		# TODO: Is there a better way to do this?
		index = 0
		for perm in self.permissions:
			if perm == name:
				del self._permissions[index]
			index += 1

	def only_permissions(self, permissions):
		"""
		Clear out all permissions on this role, and set them to be
		just the ones specified in the supplied list.

		:arg list permissions: The permissions to set for
			this role.
		"""
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
	"""
	RolePermission - a single permission that is part
	of a ``Role``.

	Don't work with this directly - use the methods on
	``Role`` itself.
	"""
	__tablename__ = 'role_permission'

	id = Column(Integer, primary_key=True)
	role_id = Column(Integer, ForeignKey('role.id'), nullable=False, index=True)
	permission = Column(String(255), nullable=False, index=True)

	def __repr__(self):
		return "<RolePermission('%s':'%s')>" % (self.role, self.permission)

	def flatten(self, field_list=None):
		return super(Node, self).flatten(['permission', 'role'])

class Workspace(OrmBase, Base):
	"""
	Workspace - a workspace for applications.

	Special Fields:

	* **tags**: This field is a dict, stored JSON
	  encoded in a text field.
	"""
	__tablename__ = 'workspace'

	id = Column(Integer, primary_key=True)
	name = Column(String(255), nullable=False, unique=True)
	stub = Column(String(255), nullable=False, unique=True)
	_tags = Column('tags', Text, nullable=True)

	def __repr__(self):
		return "<Workspace('%s')>" % self.name

	def flatten(self, field_list=None):
		return super(Workspace, self).flatten(['name', 'stub', 'tags', 'can_delete'])

	@hybrid_property
	def tags(self):
		if self._tags:
			return json.loads(self._tags)
		else:
			return {}

	@tags.setter
	def tags(self, val):
		self._tags = json.dumps(val)

	@property
	def can_delete(self):
		"""
		Workspaces can only be deleted if they have no applications.
		"""
		return len(self.applications) == 0

class WorkspaceUserRole(OrmBase, Base):
	"""
	WorkspaceUserRole - links a user and a role together,
	and, confusingly, optionally a workspace as well.

	If workspace_id is NULL, it's interpretted to mean
	that the user assigned role is global to the system.
	"""
	__tablename__ = 'workspace_user_role'

	id = Column(Integer, primary_key=True)
	# workspace_id can be null, meaning it's global.
	workspace_id = Column(Integer, ForeignKey('workspace.id'), nullable=True, index=True)
	workspace = relationship("Workspace", backref=backref('users', order_by=id, cascade="all, delete"))
	role_id = Column(Integer, ForeignKey('role.id'), index=True)
	role = relationship("Role", backref=backref('workspaces', order_by=id))
	user_id = Column(Integer, ForeignKey('user.id'), index=True)
	user = relationship("User", backref=backref('workspaces', order_by=id))

	def __repr__(self):
		return "<WorkspaceUserRole('%s'@'%s' -> '%s')>" % (self.user, self.workspace, self.role)

	def flatten(self, field_list=None):
		return super(WorkspaceUserRole, self).flatten(['workspace', 'user', 'role'])

class WorkspaceUserRoleFlat(OrmBase, Base):
	"""
	WorkspaceUserRoleFlat - a denormalisation of WorkspaceUserRole,
	Role, and RolePermission, designed to speed up permission
	lookups. Functions on this class managed clearing and
	rebuilding this table.

	Why not implement it as a trigger? The plan is to support
	as many RDBMS's as possible, and we'd need to write triggers
	for each one... maybe in a future version.
	"""
	__tablename__ = 'workspace_user_role_flat'

	# No backrefs here - this is primarily for lookup.
	id = Column(Integer, primary_key=True)
	# workspace_id can be null, meaning it's global.
	workspace_id = Column(Integer, ForeignKey('workspace.id'), nullable=True, index=True)
	workspace = relationship("Workspace", backref=backref('flatcache', order_by=id, cascade="all, delete"))
	role_id = Column(Integer, ForeignKey('role.id'), index=True)
	role = relationship("Role")
	user_id = Column(Integer, ForeignKey('user.id'), index=True)
	user = relationship("User")
	permission = Column(String(255), nullable=False, index=True)

	def __repr__(self):
		return "<WorkspaceUserRoleFlat('%s'@'%s' -> '%s')>" % (self.user, self.workspace, self.role)

	def flatten(self, field_list=None):
		return super(WorkspaceUserRoleFlat, self).flatten(['workspace', 'user', 'role'])

	@staticmethod
	def build_flat_table(session):
		"""
		Update the cache table from the current user role
		assignments. The updates are done in the context
		of the given session, and the session is committed
		before this function returns control to the caller.

		:arg Session session: The SQLAlchemy session to
			perform these updates in.
		"""
		session.query(WorkspaceUserRoleFlat).delete()
		links = session.query(
			WorkspaceUserRole
		).filter(
			WorkspaceUserRole.deleted == None
		)

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
		"""
		Quickly, by using a single SQL query, determine if the
		given user has the given permission on the given workspace.

		:arg User user: The user object to check.
		:arg str permission: The permission to check for.
		:arg Workspace|None workspace: The optional workspace
			to limit the permission to.
		"""
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

	@staticmethod
	def list_of_workspaces_for_user(session, user):
		"""
		Return a list of workspaces that the user can view,
		based on their role assignments. Uses the flat
		table to be able to return a list with a single SQL query.
		The return of this is just a list of workspace ID's - you
		will need to convert them into a list of Workspace objects
		if required.

		:arg Session session: The session to work in.
		:arg User user: The user to work for.
		"""
		# Return a list of IDs of workspaces that the given user can view.
		query = session.query(
			WorkspaceUserRoleFlat.workspace_id
		).filter(
			WorkspaceUserRoleFlat.user_id == user.id,
			WorkspaceUserRoleFlat.permission == constants.PERMISSION.WORKSPACE_VIEW
		)
		return query

class WorkspaceUserRoleFlatCache(object):
	"""
	A helper object to cache the contents of the WorkspaceUserRoleFlat
	table for a single user.

	The idea of this is that each web request might make multiple
	permission checks for a single user. Each one would normally
	require a SQL query to check that permission. As permission
	checks are used to determine what to display in the navigation,
	this would quickly get slow.

	Instead, this class, which can be shared between requests,
	cached the entire permission set for a user. On request startup,
	you can ask it to update itself - it then does a quick query to
	see if the permissions table has changed, and if so, does another
	single query to update the cached table.

	:arg User user: The user that this cache is for.
	"""
	def __init__(self, user):
		# Build our cache.
		self.cache = {}
		self.cache_version = None
		self.user = user

	def _build_cache(self, session):
		permissions = session.query(
			WorkspaceUserRoleFlat.workspace_id,
			WorkspaceUserRoleFlat.permission
		).filter(
			WorkspaceUserRoleFlat.user_id == self.user.id
		).all()

		self.cache.clear()
		logger.debug("Cache has %d values for user %d.", len(permissions), self.user.id)
		for permission in permissions:
			key = self._key(permission[1], permission[0])
			self.cache[key] = True

	def check_cache(self, session):
		"""
		Check the cache to see if it's up to date,
		and if not, update the contents.

		:arg Session session: The session to work in.
		"""
		updated = session.query(
			func.max(WorkspaceUserRoleFlat.updated)
		).scalar()
		if updated:
			comparevalue = updated.isoformat()
		else:
			comparevalue = str(uuid.uuid4())
		logging.debug("Permissions cache compare value: %s / %s", self.cache_version, comparevalue)
		if self.cache_version != comparevalue:
			# It's changed.
			self._build_cache(session)
			self.cache_version = comparevalue

	def _key(self, permission, workspace):
		return "%s_%s" % (workspace, permission)

	def has_permission(self, permission, workspace):
		"""
		Determine if the user has the appropriate permission.

		This works only on the cached values; if the cache
		has not been initialized, then this will always return false.

		The idea here is to call ``check_cache()`` on request startup,
		and then ``has_permission()`` wherever required for the remainder
		of the lifetime of the request.
		"""
		if workspace and (isinstance(workspace, int) or isinstance(workspace, long)):
			workspace_id = workspace
		elif workspace:
			workspace_id = workspace.id
		else:
			workspace_id = None
		key_normal = self._key(permission, workspace_id)
		if self.cache.has_key(key_normal):
			return True

		# Now check with no workspace.
		key_none = self._key(permission, None)
		return self.cache.has_key(key_none)

class Application(OrmBase, Base):
	"""
	Application - the top level of an application.

	Special Features:

	* There is a unique index on the name and workspace ID. This
	  means application names are unique per workspace.
	"""
	__tablename__ = 'application'
	__table_args__ = (Index('unique_app_per_workspace', "workspace_id", "name", unique=True),)

	id = Column(Integer, primary_key=True)
	workspace_id = Column(Integer, ForeignKey('workspace.id'), nullable=False, index=True)
	workspace = relationship("Workspace", backref=backref('applications', order_by=id))
	# Names are unique per workspace.
	name = Column(String(255), index=True)
	manifest_path = Column(String(255), nullable=True)

	def __repr__(self):
		return "<Application('%s')>" % self.name

	def flatten(self, field_list=None):
		return super(Application, self).flatten(['name', 'workspace_id', 'health', 'can_delete'])

	def flatten_for_heart(self):
		"""
		Return the fields that are passed along to a heart in
		the instance data.
		"""
		fields = ['name']
		return super(Application, self).flatten(fields)

	@property
	def health(self):
		"""
		Do a basic health check on this application.

		If this application has a current version, that version
		is asked about it's health and the data from that
		returned.
		"""
		current_version = self.versions.filter(ApplicationVersion.is_current == True).first()
		if current_version:
			status = current_version.health
			return status['overall']
		else:
			# It's warning, because no versions are current.
			return constants.HEALTH.WARNING

	@property
	def can_delete(self):
		"""
		Find out if this app has any versions in the READY or RUNNING states.
		If so, return false; if not, this app can be deleted safely.

		:arg Session session: SQLAlchemy session object to work in
		"""
		undeleteable_versions = self.versions.filter(
			ApplicationVersion.application == self,
			ApplicationVersion.state.in_([constants.VERSION.READY, constants.VERSION.RUNNING])
		)
		return (undeleteable_versions.count() == 0)

# Joining table between Application Version and services.
# There is no ORM object to represent this.
application_version_services = Table('application_version_service', Base.metadata,
     Column('application_version_id', Integer, ForeignKey('application_version.id')),
     Column('service_id', Integer, ForeignKey('service.id'))
)

class ApplicationVersion(OrmBase, Base):
	"""
	ApplicationVersion - a version of an application.

	Special Features:

	* **scm_parameters**: this is a dictionary that is stored
	  JSON encoded into a text field.
	* **version**: This is an integer number that increments
	  for each version. It's determined by querying the maximum
	  previous version number and returning one more.
	  ``get_next_version_number()`` handles this query.
	"""
	__tablename__ = 'application_version'

	id = Column(Integer, primary_key=True)
	application_id = Column(Integer, ForeignKey('application.id'), nullable=False, index=True)
	application = relationship("Application", backref=backref('versions', lazy="dynamic", cascade="all, delete"))
	version = Column(Integer, nullable=False)
	is_current = Column(Boolean, nullable=False)
	statistics = Column(Text, nullable=True)
	manifest = Column(Text, nullable=False)
	source_path = Column(String(255), nullable=True)
	source_checksum = Column(String(255), nullable=True)
	source_package_type = Column(String(255), nullable=True)
	scm_name = Column(String(255), nullable=False)
	_scm_parameters = Column("scm_parameters", Text, nullable=False)

	state = Column(String(255), nullable=False, index=True)

	services = relationship('Service', secondary=application_version_services, backref='application_versions')

	def __init__(self):
		self.is_current = False

	@hybrid_property
	def scm_parameters(self):
		if self._scm_parameters:
			return json.loads(self._scm_parameters)
		else:
			return {}

	@scm_parameters.setter
	def scm_parameters(self, val):
		self._scm_parameters = json.dumps(val)

	def __repr__(self):
		return "<ApplicationVersion('%s'@'%s' - active: %s)>" % (self.version, self.application, str(self.is_current))

	def flatten(self, field_list=None):
		return super(ApplicationVersion, self).flatten(['application_id', 'version', 'is_current', 'state', 'health', 'scm_name', 'scm_parameters', 'source_package_type'])

	def flatten_for_heart(self):
		"""
		Flatten data that a heart will need to execute this version.
		"""
		fields = ['version', 'source_path', 'source_checksum', 'source_package_type']
		return super(ApplicationVersion, self).flatten(fields)

	@staticmethod
	def get_next_version_number(session, application):
		"""
		For the given application, determine the next
		version number.

		:arg Session session: The session to use for this
			query.
		:arg Application application: The application to get
			the next version of.
		"""
		query = session.query(
			func.max(
				ApplicationVersion.version
			)
		).filter_by(
			application=application
		)
		value = query[0][0]
		if value:
			return value + 1
		else:
			return 1

	def get_service_credentials(self):
		"""
		Fetch all the service credentials for this version
		of the application. Returns a dict, keyed
		by the service name.
		"""
		credentials = {}
		for service in self.services:
			credentials[service.name] = service.credentials
			credentials[service.name]['provider'] = service.provider

		return credentials

	def get_current(self, session):
		"""
		From any given version of the application,
		get the current version.

		:arg Session session: The session to work in.
		"""
		current = session.query(ApplicationVersion).filter(
			ApplicationVersion.application == self.application,
			ApplicationVersion.is_current == True
		).first()

		return current

	def make_current(self, session):
		"""
		Disable all other versions of this application,
		and make this version the current version. Before
		returning control to the caller, this will commit
		the session and refresh this object.

		:arg Session session: The session to work in.
		"""
		# Disable all versions.
		session.query(ApplicationVersion).filter(
			ApplicationVersion.application == self.application
		).update(
			{
				'is_current': False
			}
		)
		session.refresh(self)
		# And allow ours to be current. Commit it all in one transaction.
		self.is_current = True
		session.add(self)
		session.commit()
		session.refresh(self)

	@property
	def health(self):
		"""
		Determine the health of this version. Returns a dict that
		describes the health of this version, by instance type.
		"""
		health = {'types': {}, 'overall': constants.HEALTH.OK}
		seen_statuses = set(constants.HEALTH.OK)
		# So, to be healthy, we need to have the right number of
		# instances of each type. If we have some running but not enough,
		# then we're warning. Otherwise, we're unhealthy.
		# However, if the version isn't running, then we're not interested.
		if self.is_current and self.state != constants.VERSION.RUNNING:
			for instance_type in self.instance_types:
				health['types'][instance_type.name] = {
					'state': constants.HEALTH.ERROR,
					'message': 'Should be running as this version is current'
				}
			seen_statuses.add(constants.HEALTH.ERROR)
		elif self.state != constants.VERSION.RUNNING:
			for instance_type in self.instance_types:
				health['types'][instance_type.name] = {
					'state': constants.HEALTH.OK,
					'message': ''
				}
		else:
			# For each instance type...
			for instance_type in self.instance_types:
				# Find the instances.
				# TODO: Write unit tests for this code.
				instances = instance_type.instances.filter(ApplicationInstance.state == constants.INSTANCE.RUNNING)
				qty = instances.count()
				if qty > 0 and instance_type.exclusive and not self.is_current:
					health['types'][instance_type.name] = {
						'state': constants.HEALTH.ERROR,
						'message': 'Exclusive instance that is not current is running.'
					}
					seen_statuses.add(constants.HEALTH.ERROR)
				elif (qty == 0 and not instance_type.exclusive) or \
						(qty == 0 and self.is_current):
					health['types'][instance_type.name] = {
						'state': constants.HEALTH.ERROR,
						'message': 'No running instances'
					}
					seen_statuses.add(constants.HEALTH.ERROR)
				elif qty < instance_type.quantity and not instance_type.exclusive:
					health['types'][instance_type.name] = {
						'state': constants.HEALTH.WARNING,
						'message': 'Not enough running instances - only %d of %d' % (qty, instance_type.quantity)
					}
					seen_statuses.add(constants.HEALTH.WARNING)
				else:
					health['types'][instance_type.name] = {
						'state': constants.HEALTH.OK,
						'message': '%d instances running' % qty
					}

		if constants.HEALTH.ERROR in seen_statuses:
			health['overall'] = constants.HEALTH.ERROR
		elif constants.HEALTH.WARNING in seen_statuses:
			health['overall'] = constants.HEALTH.WARNING

		return health

class ApplicationInstanceType(OrmBase, Base):
	"""
	ApplicationInstanceType - a class to represent each different
	instance type for a version of an application.

	Special Features:

	* Unique index on application version ID and name. This
	  prevents multiple instance types with the same name.
	* **runtime_parameters**, **startup**, and **placement_parameters**
	  are all dicts, stored JSON encoded in text fields.
	"""
	__tablename__ = 'application_instance_type'
	__table_args__ = (Index('unique_instance_type_per_version', "application_version_id", "name", unique=True),)

	id = Column(Integer, primary_key=True)
	application_version_id = Column(Integer, ForeignKey('application_version.id'), nullable=False, index=True)
	application_version = relationship("ApplicationVersion", backref=backref('instance_types', order_by=id, cascade="all, delete"))
	name = Column(String(255), nullable=False, index=True)
	quantity = Column(Integer, nullable=False)
	runtime_name = Column(Text, nullable=False)
	_runtime_parameters = Column("runtime_parameters", Text, nullable=False)
	runtime_version = Column(Text, nullable=False)
	_startup = Column("startup", Text, nullable=False)
	placement_provider = Column(Text, nullable=False)
	_placement_parameters = Column("placement_parameters", Text, nullable=False)
	exclusive = Column(Boolean, nullable=False)
	standalone = Column(Boolean, nullable=False)

	def __repr__(self):
		return "<ApplicationInstanceType('%s':'%s')>" % (self.name, self.runtime_name)

	def flatten(self, field_list=None):
		flatten = super(ApplicationInstanceType, self).flatten(['name', 'application_version_id', 'quantity', 'runtime_name', 'runtime_version', 'placement_provider', 'exclusive', 'standalone'])

		flatten['hostnames'] = []
		for hostname in self.hostnames:
			flatten['hostnames'].append(hostname.hostname)

		return flatten

	def flatten_for_heart(self):
		"""
		Return a flattened version ready for a heart to execute.
		"""
		fields = ['name', 'runtime_name', 'runtime_parameters', 'runtime_version', 'startup', 'exclusive', 'standalone']
		return super(ApplicationInstanceType, self).flatten(fields)

	def version_hostname(self, configuration):
		"""
		Return a hostname that uniquely identifies this version
		of the application. This takes into account the version,
		instance type, application, workspace, and cluster hostname.

		The output format is::

			<version>.<type>.<application>.<workspace>.<cluster hostname>
			Eg: 1.web.tornado-simple.test.local.paasmaker.net

		:arg Configuration configuration: The configuration object,
			which is used to determine the cluster hostname.
		"""
		# Format: <version>.<type>.<application>.<workspace>.<cluster hostname>
		# Eg: 1.web.tornado-simple.test.local.paasmaker.net
		type_hostname = self.type_hostname(configuration)
		instance_version_hostname = "%d.%s" % (
			self.application_version.version,
			type_hostname
		)
		instance_version_hostname = instance_version_hostname.lower()
		return instance_version_hostname

	def type_hostname(self, configuration):
		"""
		Return a hostname that uniquely identifies this instance
		type of the application. This takes into account the type,
		application, workspace, and cluster hostname.

		The output format is::

			<type>.<application>.<workspace>.<cluster hostname>
			Eg: web.tornado-simple.test.local.paasmaker.net

		:arg Configuration configuration: The configuration object,
			which is used to determine the cluster hostname.
		"""
		# Format: <type>.<application>.<workspace>.<cluster hostname>
		# Eg: web.tornado-simple.test.local.paasmaker.net
		type_hostname = "%s.%s.%s.%s" % (
			self.name,
			self.application_version.application.name,
			self.application_version.application.workspace.stub,
			configuration.get_flat('pacemaker.cluster_hostname')
		)
		type_hostname.lower()
		return type_hostname

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

	def adjustment_instances(self, session, states=constants.INSTANCE_ALLOCATED_STATES):
		"""
		Calculate and return the adjustment number of instances, taking into
		account active instances on the cluster already. This may return
		either 0, a positive number, or a negative number. If the number is
		zero, we already have enough instances. If the number is positive,
		we need more instances. If the number of negative, we have too many
		instances.

		:arg Session session: The session to do any queries in the context of.
		:arg list states: Only consider instances in this state in the calculation.
			Use this argument carefully.
		"""
		quantity = self.quantity

		# Limit to active nodes.
		active_nodes = session.query(
			Node.id
		).filter(
			Node.state == constants.NODE.ACTIVE
		)

		# Find out how many instances already exist, and subtract that
		# quantity.
		existing_quantity = session.query(
			ApplicationInstance
		).filter(
			ApplicationInstance.application_instance_type == self,
			ApplicationInstance.state.in_(states),
			ApplicationInstance.node_id.in_(active_nodes)
		).count()

		if self.exclusive and existing_quantity > 0 and not self.application_version.is_current:
			# Special handling for exclusive instances.
			# Basically, it should not be running in this condition.
			quantity = -existing_quantity
		else:
			quantity -= existing_quantity

		return quantity

class ApplicationInstance(OrmBase, Base):
	"""
	ApplicationInstance - a known instance of an instance type on
	the cluster. Binds a node and an application instance type together,
	along with it's state and other related data.

	Special Features:

	* **statistics**: a dict stored as a JSON encoded string in a text field.
	"""
	__tablename__ = 'application_instance'

	id = Column(Integer, primary_key=True)
	instance_id = Column(String(255), nullable=False, index=True)
	application_instance_type_id = Column(Integer, ForeignKey('application_instance_type.id'), nullable=False, index=True)
	application_instance_type = relationship("ApplicationInstanceType", backref=backref('instances', order_by=id, lazy="dynamic", cascade="all, delete"))
	node_id = Column(Integer, ForeignKey('node.id'), nullable=False, index=True)
	node = relationship("Node", backref=backref('instances', order_by=id, cascade="all, delete, delete-orphan"))
	port = Column(Integer, nullable=True, index=True)
	state = Column(String(255), nullable=False, index=True)
	_statistics = Column("statistics", Text, nullable=True)

	def __repr__(self):
		return "<ApplicationInstance('%s'@'%s' - %s)>" % (self.application_instance_type, self.node, self.state)

	def flatten(self, field_list=None):
		return super(ApplicationInstance, self).flatten(['instance_id', 'application_instance_type_id', 'node_id', 'state', 'port'])

	def flatten_for_heart(self):
		"""
		Gather all the data required to pass to a heart to allow
		it to be able to execute the instance. This is done because
		a heart will likely not have access to the SQL database.
		"""
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

	def get_router_location(self):
		"""
		Get the router location entry for this instance.
		The location includes an IP address, and also several
		keys that are used to account for the traffic.
		"""
		# TODO: This uses synchronous functions to do DNS
		# lookups; don't do this. It will require some
		# refactoring to fix this.
		# TODO: Replace this with an Async DNS lookup.
		# TODO: IPv6 support!

		# The format of the key is:
		# <address>:<port>#<version type id>#<node id>#<instance id>
		router_location = '%s:%d#%d#%d#%d' % (
			socket.gethostbyname(self.node.route),
			self.port,
			self.application_instance_type_id,
			self.node_id,
			self.id
		)

		return router_location

class ApplicationInstanceTypeHostname(OrmBase, Base):
	"""
	ApplicationInstanceTypeHostname - a class to encapsulate
	a hostname that is assigned to the current version of an
	application instance type.
	"""
	__tablename__ = 'application_instance_type_hostname'

	id = Column(Integer, primary_key=True)
	application_instance_type_id = Column(Integer, ForeignKey('application_instance_type.id'), nullable=False, index=True)
	application_instance_type = relationship("ApplicationInstanceType", backref=backref('hostnames', order_by=id, cascade="all, delete"))

	hostname = Column(String(255), nullable=False, index=True)
	statistics = Column(Text, nullable=True)

	def __repr__(self):
		return "<ApplicationInstanceTypeHostname('%s' -> '%s')>" % (self.hostname, self.application_instance_type)

	def flatten(self, field_list=None):
		return super(Node, self).flatten(['application_instance_type', 'hostname'])

class ApplicationInstanceTypeCron(OrmBase, Base):
	"""
	ApplicationInstanceTypeCron - a class to record a cron job
	to be run against an application instance type.
	"""
	__tablename__ = 'application_instance_type_cron'

	id = Column(Integer, primary_key=True)
	application_instance_type_id = Column(Integer, ForeignKey('application_instance_type.id'), nullable=False, index=True)
	application_instance_type = relationship("ApplicationInstanceType", backref=backref('crons', order_by=id, cascade="all, delete"))

	runspec = Column(String(255), nullable=False)
	uri = Column(Text, nullable=False)
	username = Column(Text, nullable=True)
	password = Column(Text, nullable=True)

	def __repr__(self):
		return "<ApplicationInstanceTypeCron('%s':'%s')>" % (self.runspec, self.uri)

	def flatten(self, field_list=None):
		return super(Node, self).flatten(['application_instance_type_id', 'runspec', 'uri'])

class Service(OrmBase, Base):
	"""
	Service - a class to store the details of a service,
	including it's state and the application that it belongs to.

	Special Features:

	* The name of a service is unique per application.
	* **parameters** and **credentials** are dicts, stored JSON
	  encoded as text fields.
	"""
	__tablename__ = 'service'
	__table_args__ = (Index('unique_service_per_application', "application_id", "name", unique=True),)

	id = Column(Integer, primary_key=True)
	application_id = Column(Integer, ForeignKey('application.id'), nullable=False, index=True)
	application = relationship("Application", backref=backref('services', order_by=id, cascade="all, delete"))
	name = Column(String(255), nullable=False, index=True)
	provider = Column(String(255), nullable=False, index=True)
	_parameters = Column('parameters', Text, nullable=False)
	_credentials = Column('credentials', Text, nullable=True)
	state = Column(String(255), nullable=False, index=True)

	# For future use.
	shared = Column(Boolean, nullable=False, default=False)

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
		return "<Service('%s'->'%s')>" % (self.provider, self.application)

	def flatten(self, field_list=None):
		final_field_list = ['application_id', 'name', 'provider', 'state']
		if field_list:
			final_field_list.extend(field_list)
		return super(Service, self).flatten(final_field_list)

	@staticmethod
	def get_or_create(session, application, name):
		"""
		Get an existing service with the given name in the given
		application, or create a new one and return it. New services
		are given the state NEW - it's expected that the job
		that asked for this service will handle changing it's state.
		"""
		# Find an existing one.
		service = session.query(
			Service
		).filter(
			Service.application == application,
			Service.name == name
		).first()
		if service:
			return service
		else:
			service = Service()
			service.application = application
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
		role.add_permission(constants.PERMISSION.USER_EDIT)

		s.add(user)
		s.add(role)

		s.commit()

		# TODO: APIkey isn't set until the password is set.
		# Fix this.
		s.refresh(user)
		self.assertTrue(user.apikey)

		workspace = Workspace()
		workspace.name = 'Work Zone'
		workspace.stub = 'work'
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
		self.assertEquals(len(flat.keys()), 20, "Item has incorrect number of keys - expecting %d got %d" % (20, len(flat.keys())))
		self.assertTrue(flat.has_key('id'), "Missing ID.")
		self.assertTrue(flat.has_key('name'), "Missing name.")
		self.assertTrue(isinstance(flat['id'], int), "ID is not an integer.")

		data = { 'node': item }
		encoded = json.dumps(data, cls=paasmaker.util.jsonencoder.JsonEncoder)
		decoded = json.loads(encoded)

		self.assertEquals(decoded['node']['id'], 1, "ID is not correct.")

	def test_password_hashing(self):
		s = self.session

		user = User()
		user.login = 'username'
		user.email = 'username@example.com'
		user.password = 'test'

		s.add(user)
		s.commit()

		self.assertTrue(user.check_password('test'), "Password couldn't be verified.")
		self.assertFalse(user.check_password('test1'), "Different password was correct.")
		self.assertEquals(user.password[0], '$', "Password is not in correct format.")

		# Force old style hashing, to make sure that old passwords
		# still validate.
		user.auth_meta = {'salt': str(uuid.uuid4())}
		user._password = user.password_hash('test')

		self.assertTrue(user.check_password('test'), "Old password can not be verified.")
		self.assertFalse(user.check_password('test1'), "Different password was correct.")
		self.assertNotEquals(user.password[0], '$', "Password is not in correct format.")

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
		workspace.stub = 'work'
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

		# Create a cache for the user.
		cache = WorkspaceUserRoleFlatCache(user)
		cache.check_cache(s)

		# Do some basic tests.
		has_permission = WorkspaceUserRoleFlat.has_permission(
			s,
			user,
			constants.PERMISSION.WORKSPACE_VIEW,
			workspace
		)
		cache_has_permission = cache.has_permission(
			constants.PERMISSION.WORKSPACE_VIEW,
			workspace
		)
		self.assertTrue(has_permission, "Unable to view workspace.")
		self.assertTrue(cache_has_permission, "Unable to view workspace.")
		has_permission = WorkspaceUserRoleFlat.has_permission(
			s,
			user,
			constants.PERMISSION.WORKSPACE_EDIT,
			workspace
		)
		cache_has_permission = cache.has_permission(
			constants.PERMISSION.WORKSPACE_EDIT,
			workspace
		)
		self.assertFalse(has_permission, "Can create workspace.")
		self.assertFalse(cache_has_permission, "Can create workspace.")
		has_permission = WorkspaceUserRoleFlat.has_permission(
			s,
			user,
			constants.PERMISSION.WORKSPACE_VIEW,
			None
		)
		cache_has_permission = cache.has_permission(
			constants.PERMISSION.WORKSPACE_VIEW,
			None
		)
		self.assertFalse(has_permission, "Can view workspace on global level.")
		self.assertFalse(cache_has_permission, "Can view workspace on global level.")
		has_permission = WorkspaceUserRoleFlat.has_permission(
			s,
			user,
			constants.PERMISSION.WORKSPACE_EDIT,
			None
		)
		cache_has_permission = cache.has_permission(
			constants.PERMISSION.WORKSPACE_EDIT,
			None
		)
		self.assertFalse(has_permission, "Can create workspace.")
		self.assertFalse(cache_has_permission, "Can create workspace.")

		# Revoke permission, then try again.
		role.remove_permission(constants.PERMISSION.WORKSPACE_VIEW)
		s.add(role)
		s.commit()
		WorkspaceUserRoleFlat.build_flat_table(s)
		cache.check_cache(s)

		has_permission = WorkspaceUserRoleFlat.has_permission(
			s,
			user,
			constants.PERMISSION.WORKSPACE_VIEW,
			workspace
		)
		cache_has_permission = cache.has_permission(
			constants.PERMISSION.WORKSPACE_VIEW,
			None
		)
		self.assertFalse(has_permission, "Can view workspace.")
		self.assertFalse(cache_has_permission, "Can view workspace.")
		has_permission = WorkspaceUserRoleFlat.has_permission(
			s,
			user,
			constants.PERMISSION.WORKSPACE_VIEW,
			None
		)
		cache_has_permission = cache.has_permission(
			constants.PERMISSION.WORKSPACE_VIEW,
			None
		)
		self.assertFalse(has_permission, "Can view workspace on global level.")
		self.assertFalse(cache_has_permission, "Can view workspace on global level.")

		# Now set the permissions using the array whole set method.
		role.permissions = [constants.PERMISSION.WORKSPACE_VIEW]
		s.add(role)
		s.commit()
		WorkspaceUserRoleFlat.build_flat_table(s)
		cache.check_cache(s)

		has_permission = WorkspaceUserRoleFlat.has_permission(
			s,
			user,
			constants.PERMISSION.WORKSPACE_VIEW,
			workspace
		)
		cache_has_permission = cache.has_permission(
			constants.PERMISSION.WORKSPACE_VIEW,
			workspace
		)
		self.assertTrue(has_permission, "Can't view workspace.")
		self.assertTrue(cache_has_permission, "Can't view workspace.")

		# Now assign a global permission.
		role_global = Role()
		role_global.name = 'Global Level'
		role_global.add_permission(constants.PERMISSION.USER_EDIT)

		s.add(role_global)

		wuglobal = WorkspaceUserRole()
		wuglobal.user = user
		wuglobal.role = role_global
		s.add(wuglobal)
		s.commit()

		# Rebuild the permissions table.
		WorkspaceUserRoleFlat.build_flat_table(s)
		cache.check_cache(s)

		has_permission = WorkspaceUserRoleFlat.has_permission(
			s,
			user,
			constants.PERMISSION.USER_EDIT,
			workspace
		)
		cache_has_permission = cache.has_permission(
			constants.PERMISSION.USER_EDIT,
			workspace
		)
		self.assertTrue(has_permission, "Can't create user.")
		self.assertTrue(cache_has_permission, "Can't create user.")
		has_permission = WorkspaceUserRoleFlat.has_permission(
			s,
			user,
			constants.PERMISSION.USER_EDIT,
			None
		)
		cache_has_permission = cache.has_permission(
			constants.PERMISSION.USER_EDIT,
			None
		)
		self.assertTrue(has_permission, "Can't create user.")
		self.assertTrue(cache_has_permission, "Can't create user.")

		user_two = User()
		user_two.login = 'username_two'
		user_two.email = 'username_two@example.com'
		user_two.password = 'test'
		s.add(user_two)
		s.commit()

		# Rebuild the permissions table.
		WorkspaceUserRoleFlat.build_flat_table(s)
		cache.check_cache(s)
		u2_cache = WorkspaceUserRoleFlatCache(user_two)
		u2_cache.check_cache(s)

		# And make sure that new user can't do anything.
		has_permission = WorkspaceUserRoleFlat.has_permission(
			s,
			user_two,
			constants.PERMISSION.USER_EDIT,
			workspace
		)
		cache_has_permission = u2_cache.has_permission(
			constants.PERMISSION.USER_EDIT,
			workspace
		)
		self.assertFalse(has_permission, "Can create user.")
		self.assertFalse(cache_has_permission, "Can create user.")
		has_permission = WorkspaceUserRoleFlat.has_permission(
			s,
			user_two,
			constants.PERMISSION.USER_EDIT,
			None
		)
		cache_has_permission = u2_cache.has_permission(
			constants.PERMISSION.USER_EDIT,
			None
		)
		self.assertFalse(has_permission, "Can create user.")
		self.assertFalse(cache_has_permission, "Can create user.")

		# TODO: Think of more imaginitive ways that this
		# very very simple permissions system can be broken,
		# and test them.

	def test_application_create_and_delete(self):
		session = self.session

		workspace = paasmaker.model.Workspace()
		workspace.name = 'Test'
		workspace.stub = 'test'

		application = paasmaker.model.Application()
		application.workspace = workspace
		application.name = 'foo.com'

		service = paasmaker.model.Service()
		service.application = application
		service.name = 'test'
		service.provider = 'paasmaker.service.parameters'
		service.parameters = {'test': 'bar'}
		service.credentials = {'test': 'bar'}
		service.state = paasmaker.common.core.constants.SERVICE.AVAILABLE

		application_version = paasmaker.model.ApplicationVersion()
		application_version.application = application
		application_version.version = 1
		application_version.is_current = False
		application_version.manifest = ''
		application_version.source_path = "paasmaker://testnode/foobar"
		application_version.source_checksum = 'dummychecksumhere'
		application_version.source_package_type = 'tarball'
		application_version.state = paasmaker.common.core.constants.VERSION.PREPARED
		application_version.scm_name = 'paasmaker.scm.zip'
		application_version.scm_parameters = {}

		application_version.services.append(service)

		instance_type = paasmaker.model.ApplicationInstanceType()
		instance_type.application_version = application_version
		instance_type.name = 'web'
		instance_type.quantity = 1
		instance_type.runtime_name = "paasmaker.runtime.shell"
		instance_type.runtime_parameters = {}
		instance_type.runtime_version = "1"
		instance_type.startup = {}
		instance_type.placement_provider = 'paasmaker.placement.default'
		instance_type.placement_parameters = {}
		instance_type.exclusive = False
		instance_type.standalone = False

		session.add(instance_type)

		node = paasmaker.model.Node(name='test1337',
				route='1337.local.paasmaker.net',
				apiport=12345,
				uuid="foobar-test-node",
				state=paasmaker.common.core.constants.NODE.ACTIVE)
		node.heart = True
		node.pacemaker = True
		node.tags = {}

		session.add(node)

		instance = paasmaker.model.ApplicationInstance()
		instance.instance_id = str(uuid.uuid4())
		instance.application_instance_type = instance_type
		instance.node = node
		instance.state = paasmaker.common.core.constants.INSTANCE.ALLOCATED

		session.add(instance)
		session.commit()

		session.delete(application)
		session.commit()


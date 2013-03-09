
import paasmaker

import colander
import tornado.testing

class DevDatabaseConfigurationSchema(colander.MappingSchema):
	# User details.
	login = colander.SchemaNode(colander.String(),
		title="Login username",
		description="The login username to create.",
		missing="paasmaker",
		default="paasmaker")
	email = colander.SchemaNode(colander.String(),
		title="Email Address",
		description="The test email address to use.",
		missing="test@paasmaker.com",
		default="test@paasmaker.com")
	name = colander.SchemaNode(colander.String(),
		title="Name",
		description="The full name to use.",
		missing="Paasmaker",
		default="Paasmaker")
	# TODO: Validate minimum requirements.
	password = colander.SchemaNode(colander.String(),
		title="Password",
		description="The test password to use.",
		missing="paasmaker",
		default="paasmaker")

	# Workspace details.
	create_workspace = colander.SchemaNode(colander.Boolean(),
		title="Create Workspace",
		description="If it should create a workspace as well.",
		missing=True,
		default=True)
	workspace_name = colander.SchemaNode(colander.String(),
		title="Workspace Name",
		description="The default workspace name to create.",
		missing="Test",
		default="Test")
	# TODO: Validate this closely.
	workspace_stub = colander.SchemaNode(colander.String(),
		title="Workspace Stub",
		description="The stub for the default workspace.",
		missing="test",
		default="test")

class DevDatabasePlugin(paasmaker.util.plugin.Plugin):
	MODES = {
		paasmaker.util.plugin.MODE.STARTUP_ASYNC_PRELISTEN: None
	}
	OPTIONS_SCHEMA = DevDatabaseConfigurationSchema()
	API_VERSION = "0.9.0"

	def startup_async_prelisten(self, callback, error_callback):
		# Look for some defaults, and create them if missing.
		session = self.configuration.get_database_session()

		user = session.query(
			paasmaker.model.User
		).filter(
			paasmaker.model.User.login == self.options['login']
		).first()

		self.logger.info("************************************************************")
		self.logger.info("Running development bootstrap plugin")
		self.logger.info("----------------")

		if not user:
			# Create the user and set default name/password etc.
			new_user = True
			user = paasmaker.model.User()

			user.login = self.options['login']
			user.email = self.options['email']
			user.enabled = True
			user.name = self.options['name']
			user.password = self.options['password']

			# Record that this plugin created it.
			meta = user.auth_meta
			meta['dev_user'] = self.called_name
			user.auth_meta = meta

			self.logger.info("New user created for testing!")
			self.logger.info("username: %s", self.options['login'])
			self.logger.info("password: %s", self.options['password'])
		else:
			new_user = False

			# Make sure the user is one that this plugin created.
			meta = user.auth_meta
			if not meta.has_key('dev_user') or meta['dev_user'] != self.called_name:
				error_callback("Dev Database plugin is attempting to operate on a user that it did not create. This is not permitted.")
				return

		session.add(user)
		session.commit()

		self.logger.info("YOU SHOULD NOT BE SEEING THIS LOG MESSAGE IN PRODUCTION.")
		self.logger.info("(disable DevDatabasePlugin in paasmaker.yml to prevent this)")
		self.logger.info("************************************************************")

		if new_user:
			# Create them a role with all permissions,
			# and assign it. Only for new users.
			role = paasmaker.model.Role()
			role.name = 'Administrator'
			role.permissions = paasmaker.common.core.constants.PERMISSION.ALL

			role_allocation = paasmaker.model.WorkspaceUserRole()
			role_allocation.user = user
			role_allocation.role = role

			session.add(role)
			session.add(role_allocation)

			paasmaker.model.WorkspaceUserRoleFlat.build_flat_table(session)

			if self.options['create_workspace']:
				workspace = paasmaker.model.Workspace()
				workspace.name = self.options['workspace_name']
				workspace.stub = self.options['workspace_stub']

				session.add(workspace)
				session.commit()

		# And we're done.
		session.close()
		if new_user:
			callback("Successfully created new user.")
		else:
			callback("Updated existing user.")

class DevDatabasePluginTest(tornado.testing.AsyncTestCase):
	def setUp(self):
		super(DevDatabasePluginTest, self).setUp()
		self.configuration = paasmaker.common.configuration.ConfigurationStub(0, ['pacemaker'], io_loop=self.io_loop)

		self.configuration.plugins.register(
			'paasmaker.misc.devdatabase',
			'paasmaker.pacemaker.miscplugins.devdatabase.DevDatabasePlugin',
			{},
			'Development Database Bootstrap plugin'
		)

	def tearDown(self):
		self.configuration.cleanup()
		super(DevDatabasePluginTest, self).tearDown()

	def test_simple(self):
		# If it's run, it will just create a new test user.
		session = self.configuration.get_database_session()

		users = session.query(
			paasmaker.model.User
		)

		self.assertEquals(users.count(), 0, "Should have been no users in the database.")

		# Instantiate and run the plugin.
		plugin = self.configuration.plugins.instantiate(
			'paasmaker.misc.devdatabase',
			paasmaker.util.plugin.MODE.STARTUP_ASYNC_PRELISTEN
		)

		plugin.startup_async_prelisten(self.stop, self.stop)
		self.wait()

		self.assertEquals(users.count(), 1, "Did not create test user.")

		user = users.first()

		self.assertEquals(user.login, 'paasmaker', "Wrong username.")
		self.assertEquals(user.name, 'Paasmaker', "Wrong name.")
		self.assertEquals(user.email, 'test@paasmaker.com', "Wrong Email.")
		self.assertEquals(user.auth_meta['dev_user'], 'paasmaker.misc.devdatabase', "Missing dev user flag.")

		workspaces = session.query(
			paasmaker.model.Workspace
		)
		roles = session.query(
			paasmaker.model.Role
		)
		allocations = session.query(
			paasmaker.model.WorkspaceUserRole
		)
		flat = session.query(
			paasmaker.model.WorkspaceUserRoleFlat
		)

		self.assertEquals(workspaces.count(), 1, "Did not create workspace.")
		self.assertEquals(roles.count(), 1, "Did not create role.")
		self.assertEquals(allocations.count(), 1, "Did not assign role.")
		self.assertTrue(flat.count() > 0, "Did not build permissions table.")

		# Run it again. It should not change the number of users/roles/workspaces.
		plugin.startup_async_prelisten(self.stop, self.stop)
		self.wait()

		user = users.first()

		self.assertEquals(user.login, 'paasmaker', "Wrong username.")
		self.assertEquals(user.name, 'Paasmaker', "Wrong name.")
		self.assertEquals(user.email, 'test@paasmaker.com', "Wrong Email.")
		self.assertEquals(user.auth_meta['dev_user'], 'paasmaker.misc.devdatabase', "Missing dev user flag.")

		self.assertEquals(workspaces.count(), 1, "Did not create workspace.")
		self.assertEquals(roles.count(), 1, "Did not create role.")
		self.assertEquals(allocations.count(), 1, "Did not assign role.")
		self.assertTrue(flat.count() > 0, "Did not build permissions table.")

		# Make the user different.
		meta = user.auth_meta
		meta['dev_user'] = 'paasmaker.misc.internal'
		user.auth_meta = meta
		session.add(user)
		session.commit()

		plugin.startup_async_prelisten(self.stop, self.stop)
		result = self.wait()

		self.assertIn("not permitted", result, "Did not end in error.")
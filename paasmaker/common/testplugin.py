import os

from paasmaker.util.plugin import Plugin
from paasmaker.util.plugin import MODE

import colander

class TestPluginOptionsSchema(colander.MappingSchema):
	option = colander.SchemaNode(colander.String(), default="Test", missing="Test")

class TestPluginParametersSchema(colander.MappingSchema):
	parameter = colander.SchemaNode(colander.String(), default="Test", missing="Test")

class TestPlugin(Plugin):
	"""
	A simple dummy plugin, based on the PluginExample, for use in unit tests.
	"""
	MODES = {
		MODE.TEST_PARAM: TestPluginParametersSchema(),
		MODE.TEST_NOPARAM: None,

		MODE.STARTUP_ASYNC_PRELISTEN: None,
		MODE.STARTUP_ASYNC_POSTLISTEN: None,
		MODE.STARTUP_ROUTES: None,

		MODE.SHUTDOWN_PRENOTIFY: None,
		MODE.SHUTDOWN_POSTNOTIFY: None,

		MODE.SERVICE_CREATE: TestPluginParametersSchema(),
		MODE.SERVICE_DELETE: None,

		MODE.RUNTIME_STARTUP: TestPluginParametersSchema(),
		MODE.RUNTIME_EXECUTE: TestPluginParametersSchema(),
		MODE.RUNTIME_VERSIONS: None,
		MODE.RUNTIME_ENVIRONMENT: TestPluginParametersSchema(),

		MODE.SCM_EXPORT: TestPluginParametersSchema(),
		MODE.SCM_FORM: None,
		MODE.SCM_LIST: None,

		MODE.PREPARE_COMMAND: TestPluginParametersSchema(),

		MODE.PLACEMENT: TestPluginParametersSchema(),

		MODE.USER_AUTHENTICATE_PLAIN: None,
		MODE.USER_AUTHENTICATE_EXTERNAL: None,

		MODE.JOB: TestPluginParametersSchema(),

		MODE.HEALTH_CHECK: TestPluginParametersSchema(),
		MODE.PERIODIC: None,

		MODE.NODE_DYNAMIC_TAGS: None,
		MODE.NODE_STATS: None,
		MODE.NODE_SCORE: None,

		MODE.PACKER: None,
		MODE.UNPACKER: None,
		MODE.FETCHER: None,
		MODE.STORER: None
	}
	OPTIONS_SCHEMA = TestPluginOptionsSchema()

	def do_nothing(self):
		pass

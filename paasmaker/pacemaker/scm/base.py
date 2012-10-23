
import uuid
import os
import re

import paasmaker

import tornado.testing
import colander

class BaseSCMConfigurationSchema(colander.MappingSchema):
	# No options defined.
	pass

class BaseSCMParametersSchema(colander.MappingSchema):
	# Must have a location parameter.
	location = colander.SchemaNode(colander.String(),
		title="Location of source",
		description="The location to fetch the source code from - typically a URL of some kind.")

class BaseSCM(paasmaker.util.plugin.PluginMixin):
	def get_options_schema(self):
		return BaseSCMConfigurationSchema()
	def get_parameters_schema(self):
		return BaseSCMParametersSchema()

	def get_this_scm_path(self, postfix):
		scratch_path = self.configuration.get_flat('scratch_directory')
		path = os.path.join(scratch_path, 'scm', self.__class__.__name__, postfix)
		if not os.path.exists(path):
			os.makedirs(path, 0750)

		return path

	def get_temporary_scm_dir(self):
		"""
		Get a temporary directory to unpack the source into.
		"""
		random = str(uuid.uuid4())
		return self.get_this_scm_path(random)

	def get_persistent_scm_dir(self):
		"""
		Get a persistent directory to unpack the source into.
		This is designed for SCMs that can update their code,
		so can be persistent between SCM runs.
		"""
		name = self.raw_parameters['location']
		name = re.sub(r'[^.A-Za-z]', '_', name)
		name = name.replace("__", "_")
		name = name.replace("__", "_")
		return self.get_this_scm_path(name)

class BaseSCMTest(tornado.testing.AsyncTestCase):
	def setUp(self):
		super(BaseSCMTest, self).setUp()
		self.configuration = paasmaker.common.configuration.ConfigurationStub(0, ['pacemaker'], io_loop=self.io_loop)
		self.path = None
		self.success = None
		self.message = None

	def tearDown(self):
		self.configuration.cleanup()
		super(BaseSCMTest, self).tearDown()

	def success_callback(self, path, message):
		self.success = True
		self.message = message
		self.path = path
		self.stop()

	def failure_callback(self, message):
		self.success = False
		self.message = message
		self.path = None
		self.stop()
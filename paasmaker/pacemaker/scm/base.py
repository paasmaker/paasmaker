
import uuid
import os
import re

import paasmaker

import tornado
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

# TODO: Document that SCM plugins should emit the following into the
# context tree, and it will be stored along with the other SCM params:
#  scm['revision']: the revision used.
#  scm['tool_version']: the version of the tool used (eg, version of GIT)
# This dict is merged with the SCM params supplied by the user, so you
# can use this cleverly to store only a few extra details.

class BaseSCM(paasmaker.util.plugin.Plugin):
	# These are defaults - you should set your own.
	MODES = {
		paasmaker.util.plugin.MODE.SCM_EXPORT: BaseSCMParametersSchema(),
		paasmaker.util.plugin.MODE.SCM_FORM: None
	}
	OPTIONS_SCHEMA = BaseSCMConfigurationSchema()

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
		# TODO: Consider how to lock this!
		name = self.raw_parameters['location']
		name = re.sub(r'[^.A-Za-z]', '_', name)
		name = name.replace("__", "_")
		name = name.replace("__", "_")
		return self.get_this_scm_path(name)

	def get_persistent_output_dir(self):
		"""
		Get a persistent directory to output the result of repo
		into, that can be used by prepare commands to get ready.
		"""
		# TODO: Consider how to lock this!
		name = self.raw_parameters['location']
		name = re.sub(r'[^.A-Za-z]', '_', name)
		name = name.replace("__", "_")
		name = name.replace("__", "_")
		return self.get_this_scm_path(name + '_output')

	def create_working_copy(self, callback, error_callback):
		"""
		From your input parameters, create a working copy that Paasmaker can
		write to and mutate. If possible, cache whatever you can and just
		make a copy of it for Paasmaker. Call the callback with
		the new directory, and an optional dict of output parameters.
		"""
		raise NotImplementedError("You must implement create_working_copy().")

	def create_form(self, last_selections):
		"""
		Return some HTML that goes into the form to be inserted into the
		web page, for users to interact with. The supplied last_selections
		is a hash that contains what was used last time (or empty if not found).
		"""
		raise NotImplementedError("You must implement create_form().")

	def _encoded_or_default(self, selections, key, default):
		"""
		Helper function to check to see if key exists in the given
		selections dict. If it doesn't, it returns the given default
		value. Before returning the value, it's HTML escaped.
		"""
		if selections.has_key(key):
			value = selections[key]
		else:
			value = default

		return tornado.escape.xhtml_escape(value)

	def create_summary(self):
		"""
		Return a dict, with the keys being required or optional parameters,
		and the values being a short description of what should be returned
		for that value.
		"""
		raise NotImplementedError("You must implement create_summary().")

class BaseSCMTest(tornado.testing.AsyncTestCase):
	def setUp(self):
		super(BaseSCMTest, self).setUp()
		self.configuration = paasmaker.common.configuration.ConfigurationStub(0, ['pacemaker'], io_loop=self.io_loop)
		self.registry = self.configuration.plugins
		self.path = None
		self.params = {}
		self.success = None
		self.message = None

	def tearDown(self):
		self.configuration.cleanup()
		super(BaseSCMTest, self).tearDown()

	def success_callback(self, path, message, params={}):
		self.success = True
		self.message = message
		self.path = path
		self.params = params
		self.stop()

	def failure_callback(self, message):
		self.success = False
		self.message = message
		self.path = None
		self.stop()
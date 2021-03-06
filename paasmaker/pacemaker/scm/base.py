#
# Paasmaker - Platform as a Service
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#

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
	"""
	SCM plugins are responsible for fetching raw application source code,
	ready for it to be prepared and then packed for storage. It should end
	up with a new copy that can be modified.

	SCMs should cache checkouts where possible to speed up lookups. For
	example, the git SCM stores a persistent checkout, and just pulls
	new changes each time.
	"""

	# These are defaults - you should set your own.
	MODES = {
		paasmaker.util.plugin.MODE.SCM_EXPORT: BaseSCMParametersSchema(),
		paasmaker.util.plugin.MODE.SCM_FORM: None
	}
	OPTIONS_SCHEMA = BaseSCMConfigurationSchema()

	def _get_this_scm_path(self, postfix):
		scratch_path = self.configuration.get_flat('scratch_directory')
		path = os.path.join(scratch_path, 'scm', self.__class__.__name__, postfix)
		if not os.path.exists(path):
			os.makedirs(path, 0750)

		return path

	def _get_temporary_scm_dir(self):
		"""
		Get a temporary directory to unpack the source into.
		"""
		random = str(uuid.uuid4())
		return self._get_this_scm_path(random)

	def _get_persistent_scm_dir(self):
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
		return self._get_this_scm_path(name)

	def _get_persistent_output_dir(self):
		"""
		Get a persistent directory to output the result of repo
		into, that can be used by prepare commands to get ready.
		"""
		# TODO: Consider how to lock this!
		name = self.raw_parameters['location']
		name = re.sub(r'[^.A-Za-z]', '_', name)
		name = name.replace("__", "_")
		name = name.replace("__", "_")
		return self._get_this_scm_path(name + '_output')

	def create_working_copy(self, callback, error_callback):
		"""
		From your input parameters, create a working copy that Paasmaker can
		write to and mutate. If possible, cache whatever you can and just
		make a copy of it for Paasmaker. Call the callback with
		the new directory, and an optional dict of output parameters.
		"""
		raise NotImplementedError("You must implement create_working_copy().")

	def create_summary(self):
		"""
		Return a dict, with the keys being required or optional parameters,
		and the values being a short description of what should be returned
		for that value.
		"""
		raise NotImplementedError("You must implement create_summary().")

	def abort(self):
		"""
		Helper function called by the code that invoked this SCM, indicating
		that it should abort it's processing and clean up, if it can.

		Subclasses should override ``_abort()`` instead of this function.
		"""
		self.aborted = True

		self._abort()

	def _abort(self):
		# By default... do nothing.
		pass

	def _is_aborted(self):
		if self.hasattr(self, 'aborted'):
			return self.aborted
		else:
			return False

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
		self.configuration.cleanup(self.stop, self.stop)
		self.wait()
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
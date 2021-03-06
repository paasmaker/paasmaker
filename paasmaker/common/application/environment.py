#
# Paasmaker - Platform as a Service
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#

import os
import copy
import json

class ApplicationEnvironment(object):
	"""
	A helper class that contains methods to build the environment
	variables that an application will require at runtime.
	"""

	@staticmethod
	def get_instance_environment(version):
		"""
		Fetch only the instance environment that is not node specific.
		Intended only to capture data that can be seralized and passed to
		a different node, during registration of instances with heart nodes.

		Returns a dict of the additional environment variables.

		:arg ApplicationVersion version: The version of the application to
			prepare the environment for.
		"""
		environment = {}

		# Services first.
		credentials = version.get_service_credentials()
		environment['PM_SERVICES'] = json.dumps(credentials)

		# And the rest is rolled up into a single environment variable.
		meta = {}

		# Workspace parameters.
		meta['workspace'] = version.application.workspace.tags
		meta['application'] = {
			'application_id': version.application.id,
			'name': version.application.name,
			'workspace': version.application.workspace.name,
			'workspace_stub': version.application.workspace.stub,
			'version': version.version,
			'version_id': version.id
		}

		environment['PM_METADATA'] = json.dumps(meta)

		return environment

	@staticmethod
	def merge_local_environment(configuration, other_environment):
		"""
		Merge an application's environment with this nodes environment -
		that means this nodes's tags and local environment. This should
		then form a complete set of environment variables for an application
		to start up.

		:arg Configuration configuration: The configuration object, to read
			in any other appropriate data.
		:arg dict other_environment: The environment passed from the
			pacemaker.
		"""
		environment = copy.deepcopy(other_environment)

		# Add in our nodes tags.
		meta = {}
		if environment.has_key('PM_METADATA'):
			meta = json.loads(environment['PM_METADATA'])
		meta['node'] = configuration['tags']
		environment['PM_METADATA'] = json.dumps(meta)

		# Finally, add in environment from the current process.
		for key, value in os.environ.iteritems():
			environment[key] = value

		return environment

	@staticmethod
	def get_environment(configuration, version):
		"""
		Get the entire environment required for a version, including the local
		environment. The results of this function are for use only on the
		calling node, and should not be sent to another node.

		:arg Configuration configuration: The configuration object
			to read additional data from.
		:arg ApplicationVersion version: The version ORM object to
			fetch everything from.
		"""
		# Helper to get the instance environment and our local environment in one go.
		environment = ApplicationEnvironment.get_instance_environment(version)
		environment = ApplicationEnvironment.merge_local_environment(configuration, environment)

		return environment
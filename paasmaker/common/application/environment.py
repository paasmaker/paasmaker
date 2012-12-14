
import os
import copy
import json

class ApplicationEnvironment(object):
	@staticmethod
	def get_instance_environment(version):
		"""
		Fetch only the instance environment that is not node specific.
		Intended only to capture data that can be seralized and passed to
		a different node.
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
		that means this nodes's tags and local environment.
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
		"""
		# Helper to get the instance environment and our local environment in one go.
		environment = ApplicationEnvironment.get_instance_environment(version)
		environment = ApplicationEnvironment.merge_local_environment(configuration, environment)

		return environment
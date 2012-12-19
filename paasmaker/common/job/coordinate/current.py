
import os
import subprocess
import uuid

import paasmaker
from paasmaker.common.core import constants
from ..base import BaseJob
from ...testhelpers import TestHelpers
from instancerootbase import InstanceRootBase
from instancejobhelper import InstanceJobHelper
from paasmaker.util.plugin import MODE

import tornado

# TODO: This comment is wrong. Update it and enhance it.
# We're trying to build a job tree like this:
# - Root
#   - Job Builder
# - Update database to have right version current.
#   - Remove old instances
#     - Remove A
#     - Remove B
#     - Add new current instances.
#       - Add A
#       - Add B
#         - TODO: Startup exclusive instances.
#           - Start A
#           - Start B
#             - TODO: Shutdown exclusive instances.
#               - Stop A
#               - Stop B
# TODO: Extend this to start/stop exclusive instances,
# as shown by the TODO jobs in the list above.

class CurrentVersionRequestJob(InstanceJobHelper):

	@staticmethod
	def setup_version(configuration, application_version_id, callback):
		session = configuration.get_database_session()
		context = {}
		context['application_version_id'] = application_version_id

		session = configuration.get_database_session()
		new_version = session.query(paasmaker.model.ApplicationVersion).get(application_version_id)

		def on_root_job_added(root_job_id):
			callback(root_job_id)

		configuration.job_manager.add_job(
			'paasmaker.job.coordinate.currentrequest',
			{},
			"Make version %d current for %s" % (new_version.version, new_version.application.name),
			on_root_job_added,
			context=context
		)
		session.close()

	def start_job(self, context):
		self.logger.info("Starting to prepare tasks to make a version current.")
		session = self.configuration.get_database_session()

		new_version = session.query(
			paasmaker.model.ApplicationVersion
		).get(
			context['application_version_id']
		)
		current_version = new_version.get_current(session)

		self.logger.info("New version of %s: %d", new_version.application.name, new_version.version)
		if current_version:
			self.logger.info("Current version: %d", current_version.version)
		else:
			self.logger.info("No current version of this application.")

		# This is where we need to set the current version.
		self.logger.info("Marking new version as current.")
		new_version.make_current(session)

		# Containers for the other jobs.
		# The remove_container is the root of the jobs that we add.
		remove_container = self.configuration.job_manager.get_specifier()
		remove_container.set_job(
			'paasmaker.job.container',
			{},
			"Remove old instances from routing"
		)

		add_container = remove_container.add_child()
		add_container.set_job(
			'paasmaker.job.container',
			{},
			"Add new instances to routing"
		)

		tags = set()

		# On the remove container, remove all of the current versions.
		# This will actually execute after the add for the new instances.
		if current_version and current_version.id != new_version.id:
			for instance_type in current_version.instance_types:
				tags = tags.union(set(self.get_tags_for(instance_type)))

				instances = self.get_instances(
					session,
					instance_type,
					[constants.INSTANCE.RUNNING]
				)

				for instance in instances:
					remover = remove_container.add_child()
					remover.set_job(
						'paasmaker.job.routing.update',
						{
							'instance_id': instance.id,
							'add': True
						},
						"Update routing for %s" % instance.instance_id[0:8],
					)

		# For the add container, add all the current versions.
		for instance_type in new_version.instance_types:
			tags = tags.union(set(self.get_tags_for(instance_type)))

			instances = self.get_instances(
				session,
				instance_type,
				[constants.INSTANCE.RUNNING]
			)

			for instance in instances:
				adder = add_container.add_child()
				adder.set_job(
					'paasmaker.job.routing.update',
					{
						'instance_id': instance.id,
						'add': True
					},
					"Update routing for %s" % instance.instance_id[0:8],
				)

		def on_tree_executable():
			self.success({}, "Created all current switchover jobs.")

		def on_tree_added(root_id):
			self.configuration.job_manager.allow_execution(self.job_metadata['root_id'], callback=on_tree_executable)

		# Insert the tags into the remove container job.
		# TODO: This uses private data to do this.
		remove_container.parameters['tags'] = tags

		# Add that entire tree into the job manager.
		self.configuration.job_manager.add_tree(remove_container, on_tree_added, parent=self.job_metadata['root_id'])
		session.close()
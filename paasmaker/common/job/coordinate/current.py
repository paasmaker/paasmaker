
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

# We're trying to build a job tree like this:
# - Root
#   - Job Builder
# - Update database to have right version current.
#   - Remove old instances container
#     - Remove A
#     - Remove B
#     - Add new current instances container.
#       - Add A
#       - Add B
#       - Optional: Exclusive Startup/Shutdown Container
#         - Exclusive startup container
#           - Start A + routing
#             - Register
#               - Select locations
#           - Start B + routing
#           - Exclusive shutdown container
#             - Stop A + routing
#             - Stop B + routing
# TODO: Thoroughly test the exclusive instance handling.

class CurrentVersionRequestJob(InstanceJobHelper):
	"""
	A job to make a specific version of an application the current one.

	This will adjust routing, and start and stop exclusive instances
	to ensure the system ends up in the correct state.
	"""

	@staticmethod
	def setup_version(configuration, application_version_id, callback, parent=None):
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
			context=context,
			parent=parent
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

		exclusive_container = None
		exclusive_shutdown_container = None
		exclusive_startup_container = None

		tags = set()

		# On the remove container, remove all of the current versions.
		# This will actually execute after the add for the new instances.
		if current_version and current_version.id != new_version.id:
			for instance_type in current_version.instance_types:
				tags = tags.union(set(self.get_tags_for(instance_type)))

				instances = self.get_instances(
					session,
					instance_type,
					[constants.INSTANCE.RUNNING],
					context
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

			if instance_type.exclusive:
				# This is an exclusive instance. Therefore, we need to
				# shut down existing versions first, then start up the new
				# versions.
				if not exclusive_container:
					# Create a container for all the jobs, only when
					# encountering the first exclusive instance type.
					exclusive_container = add_container.add_child()
					exclusive_container.set_job(
						'paasmaker.job.container',
						{},
						"Start and stop exclusive instances"
					)

					# Jobs to select locations for starting exclusive instances,
					# if required.
					parameters = {}
					parameters['application_instance_type_id'] = instance_type.id

					exclusive_startup_container = exclusive_container.add_child()
					exclusive_startup_container.set_job(
						'paasmaker.job.coordinate.startuprequest',
						parameters,
						"Startup requests for %s" % instance_type.name
					)

					registerer = exclusive_startup_container.add_child()
					registerer.set_job(
						'paasmaker.job.coordinate.registerrequest',
						parameters,
						"Registration requests for %s" % instance_type.name
					)

					selectlocations = registerer.add_child()
					selectlocations.set_job(
						'paasmaker.job.coordinate.selectlocations',
						parameters,
						"Select instance locations for %s" % instance_type.name,
					)

					exclusive_shutdown_container = exclusive_startup_container.add_child()
					exclusive_shutdown_container.set_job(
						'paasmaker.job.container',
						{},
						"Shutdown exclusive instances"
					)

				# Now, shutdown instances of the current version.
				if current_version and current_version.id != new_version.id:
					output_current_version_instance_type = None
					# Find the matching instance type in the current version.
					# It might not exist, because that version may not have
					# an instance type with the same name.
					for current_version_instance_type in current_version.instance_types:
						if current_version_instance_type.name == instance_type.name:
							output_current_version_instance_type = current_version_instance_type

					if output_current_version_instance_type:
						instances = self.get_instances(
							session,
							output_current_version_instance_type,
							[constants.INSTANCE.RUNNING, constants.INSTANCE.STARTING],
							context
						)

						for instance in instances:
							shutdown = exclusive_shutdown_container.add_child()
							shutdown.set_job(
								'paasmaker.job.heart.shutdown',
								{
									'instance_id': instance.instance_id
								},
								"Shutdown instance %s on node %s" % (instance.instance_id, instance.node.name),
								node=instance.node.uuid
							)

							routing = shutdown.add_child()
							routing.set_job(
								'paasmaker.job.routing.update',
								{
									'instance_id': instance.id,
									'add': False
								},
								"Update routing for %s" % instance.instance_id
							)
			else:
				# Non-exclusive instance type.
				instances = self.get_instances(
					session,
					instance_type,
					[constants.INSTANCE.RUNNING],
					context
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
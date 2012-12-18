
import os
import subprocess
import uuid

import paasmaker
from paasmaker.common.core import constants
from ..base import BaseJob
from ...testhelpers import TestHelpers
from instancerootbase import InstanceRootBase

import tornado

# We're trying to build a job tree like this:
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

class CurrentVersionContainerJob(BaseJob):
	def start_job(self, context):
		self.logger.info("Sub tasks complete.")
		self.success({}, "Sub tasks completed.")

class CurrentVersionRootJob(InstanceRootBase):

	@staticmethod
	def setup_version(configuration, application_version_id, callback):
		session = configuration.get_database_session()
		context = {}
		context['application_version_id'] = application_version_id

		# TODO: Add more unit tests to this code.
		# Specifically:
		# - Switching between different versions of an application.
		# - Switching to the same version - the code does take this into
		#   account, but some really weird bugs made this not work properly.

		# Get the current version.
		# Current version can be none, in which case we don't have to do some parts of the work.
		new_version = session.query(paasmaker.model.ApplicationVersion).get(application_version_id)
		current_version = new_version.get_current(session)

		# TODO: Handle the case where the new version is the current version.
		# Because this could end badly.
		tags = set()

		# List all the instance types - new version.
		instance_types_new = []
		for instance_type in new_version.instance_types:
			instance_types_new.append(instance_type.id)
			tags = tags.union(set(InstanceRootBase.get_tags_for(configuration, instance_type.id)))
		instance_types_new.reverse()

		# List all the instance types - current version.
		# TODO: Instead of just the current version, list all versions
		# other than this version, to ensure that the routing table is completely
		# correct, in case of other failures.
		instance_types_current = []
		if current_version and current_version.id != new_version.id:
			for instance_type in current_version.instance_types:
				instance_types_current.append(instance_type.id)
				tags = tags.union(set(InstanceRootBase.get_tags_for(configuration, instance_type.id)))
			instance_types_current.reverse()

		# This is where we need to set the current version.
		new_version.make_current(session)

		def on_root_job_added(root_job_id):
			def on_remove_root_added(remove_root_id):
				def on_add_root_added(add_root_id):
					def on_remove_instances_complete():
						def on_add_instances_complete():
							# Madness over - we're done.
							callback(root_job_id)
							# end on_add_instances_complete()

						all_instances_new = []
						for instance_type_id in instance_types_new:
							all_instances_new.extend(
								InstanceRootBase.get_instances_for(
									configuration,
									instance_type_id,
									[constants.INSTANCE.RUNNING]
								)
							)

						CurrentVersionRootJob.process_routing_list(
							configuration,
							all_instances_new,
							add_root_id,
							on_add_instances_complete
						)
						# end on_remove_instances_complete

					all_instances_current = []
					for instance_type_id in instance_types_current:
						all_instances_current.extend(
							InstanceRootBase.get_instances_for(
								configuration,
								instance_type_id,
								[constants.INSTANCE.RUNNING]
							)
						)

					CurrentVersionRootJob.process_routing_list(
						configuration,
						all_instances_current,
						remove_root_id,
						on_remove_instances_complete
					)
					# end on_add_root_added

				configuration.job_manager.add_job(
					'paasmaker.job.coordinate.currentcontainer',
					{},
					"Add instances to routing",
					on_add_root_added,
					parent=remove_root_id
				)
				# end on_remove_root_added

			# Add a container for the remove jobs.
			configuration.job_manager.add_job(
				'paasmaker.job.coordinate.currentcontainer',
				{},
				"Remove instances from routing",
				on_remove_root_added,
				parent=root_job_id
			)
			# end on_root_job_added

		configuration.job_manager.add_job(
			'paasmaker.job.coordinate.currentroot',
			{},
			"Make version %d current for %s" % (new_version.version, new_version.application.name),
			on_root_job_added,
			context=context,
			tags=tags
		)

	@staticmethod
	def process_routing_list(configuration, instances, parent_id, callback):
		# Now go through the list and add sub jobs.
		def add_job(instance):
			def job_added(job_id):
				# Try the next one.
				try:
					add_job(instances.pop())
				except IndexError, ex:
					callback()

			configuration.job_manager.add_job(
				'paasmaker.job.routing.update',
				{
					'instance_id': instance['id'],
					'add': True
				},
				"Update routing for %s" % instance['instance_id'][0:8],
				job_added,
				parent=parent_id
			)

		if len(instances) > 0:
			add_job(instances.pop())
		else:
			callback()

	def start_job(self, context):
		self.logger.info("Making version current.")
		self.success({}, "Finished making version current.")

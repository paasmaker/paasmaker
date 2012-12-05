
import os
import subprocess
import uuid

import paasmaker
from paasmaker.common.core import constants
from ..base import BaseJob
from ...testhelpers import TestHelpers
from instancerootbase import InstanceRootBase

import tornado
from pubsub import pub

# TODO: Implement abort features for all of these jobs.

class ShutdownRootJob(BaseJob, InstanceRootBase):
	@staticmethod
	def setup(configuration, instance_type_id, callback, instances=[], parent=None):
		instance_list = InstanceRootBase.get_instances_for(
			configuration,
			instance_type_id,
			[constants.INSTANCE.RUNNING],
			instances
		)

		tags = InstanceRootBase.get_tags_for(configuration, instance_type_id)

		# For each instance, we need a job tree like this:
		# - Shutdown - Instance A (runtime startup) (on relevant node)
		#   - Routing remove A (local)
		def on_root_job_added(root_job_id):
			def all_jobs_queued():
				# All jobs have been queued.
				# Call the callback with the root job ID.
				callback(root_job_id)
				# end all_jobs_queued()

			def add_for_instance(instance):
				def on_shutdown_tree_done(routing_update_job_id):
					# Done! Now do the same for the next instance, or signal completion.
					try:
						add_for_instance(instance_list.pop())
					except IndexError, ex:
						all_jobs_queued()

				def on_shutdown_job(shutdown_job_id):
					# Now to update the routing.
					configuration.job_manager.add_job(
						'paasmaker.job.routing.update',
						{
							'instance_id': instance['id'],
							'add': False
						},
						"Update routing for %s" % instance['instance_id'],
						on_shutdown_tree_done,
						parent=shutdown_job_id
					)
					# end on_routing_update()

				# First job is to shutdown.
				configuration.job_manager.add_job(
					'paasmaker.job.heart.shutdown',
					{
						'instance_id': instance['instance_id']
					},
					"Shutdown instance %s on node %s" % (instance['instance_id'], instance['node_name']),
					on_shutdown_job,
					parent=root_job_id,
					node=instance['node_uuid']
				)
				# End add_for_instance()

			# Start the first one.
			try:
				add_for_instance(instance_list.pop())
			except IndexError, ex:
				# No jobs, proceed to the end.
				all_jobs_queued()
			# end on_root_job_added()

		configuration.job_manager.add_job(
			'paasmaker.job.coordinate.shutdownroot',
			{},
			"Shutdown up instances and alter routing",
			on_root_job_added,
			parent=parent,
			tags=tags
		)

	@staticmethod
	def setup_version(configuration, application_version, callback):
		# List all the instance types.
		# Assume we have an open session on the application_version object.
		destroyable_instance_type_list = []
		for instance_type in application_version.instance_types:
			destroyable_instance_type_list.append(instance_type)
		destroyable_instance_type_list.reverse()

		context = {}
		context['application_version_id'] = application_version.id

		def on_root_job_added(root_job_id):
			# Now go through the list and add sub jobs.
			def add_job(instance_type):
				def job_added(job_id):
					# Try the next one.
					try:
						add_job(destroyable_instance_type_list.pop())
					except IndexError, ex:
						callback(root_job_id)

				ShutdownRootJob.setup(
					configuration,
					instance_type.id,
					job_added,
					parent=root_job_id
				)

			if len(destroyable_instance_type_list) > 0:
				add_job(destroyable_instance_type_list.pop())
			else:
				# This is a bit of a bizzare condition... an
				# application with no instance types.
				callback(root_job_id)

		configuration.job_manager.add_job(
			'paasmaker.job.coordinate.shutdownroot',
			{},
			"Shutdown up instances and alter routing for %s version %d" % (application_version.application.name, application_version.version),
			on_root_job_added,
			context=context
		)

	def start_job(self, context):
		self.update_jobs_from_context(context)
		self.update_version_from_context(context, constants.VERSION.READY)

		self.logger.info("Shutdown instances and alter routing.")
		self.success({}, "Shut down instances and altered routing.")


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

class DeRegisterRootJob(BaseJob, InstanceRootBase):
	@staticmethod
	def setup(configuration, instance_type_id, callback, instances=[]):
		instance_list = InstanceRootBase.get_instances_for(
			configuration,
			instance_type_id,
			constants.INSTANCE_FINISHED_STATES,
			instances
		)

		# For each instance, we need a job tree like this:
		# - Deregister - on relevant node.
		def on_root_job_added(root_job_id):
			def all_jobs_queued():
				# All jobs have been queued.
				# Call the callback with the root job ID.
				callback(root_job_id)
				# end all_jobs_queued()

			def add_for_instance(instance):
				def on_deregister_job(deregister_job_id):
					# Done! Now do the same for the next instance, or signal completion.
					try:
						add_for_instance(instance_list.pop())
					except IndexError, ex:
						all_jobs_queued()

				# First job is to shutdown.
				configuration.job_manager.add_job(
					'paasmaker.job.heart.deregisterinstance',
					{
						'instance_id': instance['instance_id']
					},
					"Deregister instance %s on node %s" % (instance['instance_id'], instance['node_name']),
					on_deregister_job,
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
			'paasmaker.job.coordinate.deregisterroot',
			{},
			"Deregister instances on nodes",
			on_root_job_added
		)

	def start_job(self, context):
		self.update_jobs_from_context(context)

		self.logger.info("Shutdown instances and alter routing.")
		self.success({}, "Shut down instances and altered routing.")

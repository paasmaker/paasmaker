
import os
import subprocess
import uuid

import paasmaker
from paasmaker.common.core import constants
from ..base import BaseJob
from ...testhelpers import TestHelpers

import tornado
from pubsub import pub

# TODO: Implement abort features for all of these jobs.

class DeRegisterRootJob(BaseJob):
	@staticmethod
	def setup(configuration, application_instance_type_id, callback):
		# Set up the context.
		context = {}
		context['application_instance_type_id'] = application_instance_type_id

		# Find the instances that are in the STOPPED or ERROR state.
		session = configuration.get_database_session()
		instance_type = session.query(paasmaker.model.ApplicationInstanceType).get(application_instance_type_id)
		instances = session.query(
			paasmaker.model.ApplicationInstance
		).filter(
			paasmaker.model.ApplicationInstance.application_instance_type == instance_type,
			paasmaker.model.ApplicationInstance.state.in_(constants.INSTANCE_FINISHED_STATES)
		)
		instance_list = []
		for instance in instances:
			instance_list.append(
				{
					'id': instance.id,
					'instance_id': instance.instance_id,
					'node_name': instance.node.name,
					'node_uuid': instance.node.uuid
				}
			)
		instance_list.reverse()

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
			on_root_job_added,
			context=context
		)

	def start_job(self, context):
		# In the context is a list of instances and their statuses.
		# Update all those in the local database.
		session = self.configuration.get_database_session()
		for key, value in context.iteritems():
			# TODO: This is a very poor method of figuring out if the
			# key is an instance ID.
			if key.find('-') != -1:
				instance = session.query(
					paasmaker.model.ApplicationInstance
				).filter(
					paasmaker.model.ApplicationInstance.instance_id == key
				).first()

				if instance:
					# Update the instance state.
					self.logger.debug("Updating state for instance %s." % key)
					instance.state = value
					session.add(instance)

		session.commit()
		self.logger.info("Shutdown instances and alter routing.")
		self.success({}, "Shut down instances and altered routing.")

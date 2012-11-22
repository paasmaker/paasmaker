
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

class ShutdownRootJob(BaseJob):
	@staticmethod
	def setup(configuration, application_instance_type_id, callback):
		# Set up the context.
		context = {}
		context['application_instance_type_id'] = application_instance_type_id

		# Find the instances that are in the RUNNING state
		# (ie, that need starting)
		session = configuration.get_database_session()
		instance_type = session.query(paasmaker.model.ApplicationInstanceType).get(application_instance_type_id)
		instances = session.query(
			paasmaker.model.ApplicationInstance
		).filter(
			paasmaker.model.ApplicationInstance.application_instance_type == instance_type,
			paasmaker.model.ApplicationInstance.state == constants.INSTANCE.RUNNING
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

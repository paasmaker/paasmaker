
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

class StartupRootJob(BaseJob):
	@staticmethod
	def setup(configuration, application_instance_type_id, callback):
		# Set up the context.
		context = {}
		context['application_instance_type_id'] = application_instance_type_id

		# Find the instances that are in the REGISTERED state
		# (ie, that need starting)
		session = configuration.get_database_session()
		instance_type = session.query(paasmaker.model.ApplicationInstanceType).get(application_instance_type_id)
		instances = session.query(
			paasmaker.model.ApplicationInstance
		).filter(
			paasmaker.model.ApplicationInstance.application_instance_type == instance_type,
			paasmaker.model.ApplicationInstance.state.in_(constants.INSTANCE_CAN_START_STATES)
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
		# - Routing - Instance A (run locally)
		#   - Startup - Instance A (runtime startup) (on relevant node)
		#     - Pre-startup - Instance A (environment + startup commands) (on relevant node)
		def on_root_job_added(root_job_id):
			def all_jobs_queued():
				# All jobs have been queued.
				# Call the callback with the root job ID.
				callback(root_job_id)
				# end all_jobs_queued()

			def add_for_instance(instance):
				def on_startup_tree_done(select_locations_job_id):
					# Done! Now do the same for the next instance, or signal completion.
					try:
						add_for_instance(instance_list.pop())
					except IndexError, ex:
						all_jobs_queued()

				def on_startup_job(startup_job_id):
					# Now the pre-startup job.
					configuration.job_manager.add_job(
						'paasmaker.job.heart.prestartup',
						{
							'instance_id': instance['instance_id']
						},
						"Pre startup instance %s on node %s" % (instance['instance_id'], instance['node_name']),
						on_startup_tree_done,
						parent=startup_job_id,
						node=instance['node_uuid']
					)
					# end on_startup_job()

				def on_routing_update(routing_update_job_id):
					# Now the startup job.
					configuration.job_manager.add_job(
						'paasmaker.job.heart.startup',
						{
							'instance_id': instance['instance_id']
						},
						"Startup instance %s on node %s" % (instance['instance_id'], instance['node_name']),
						on_startup_job,
						parent=routing_update_job_id,
						node=instance['node_uuid']
					)
					# end on_routing_update()

				# First job is to update the routing.
				configuration.job_manager.add_job(
					'paasmaker.job.routing.update',
					{
						'instance_id': instance['id'],
						'add': True
					},
					"Update routing for %s" % instance['instance_id'],
					on_routing_update,
					parent=root_job_id
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
			'paasmaker.job.coordinate.startuproot',
			{},
			"Start up instances and alter routing",
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
					self.logger.debug("Updating state for instance %s." % key)
					# Update the instance state.
					instance.state = value
					session.add(instance)

		session.commit()
		self.logger.info("Startup instances and alter routing.")
		self.success({}, "Started up instances and altered routing.")

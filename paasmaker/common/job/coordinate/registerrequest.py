
import uuid

import paasmaker
from paasmaker.common.core import constants
from ..base import BaseJob
from paasmaker.util.plugin import MODE

import tornado
from pubsub import pub
import sqlalchemy

import colander

class RegisterRequestJob(BaseJob):
	def start_job(self, context):
		self.logger.info("Creating node registration jobs.")

		self.session = self.configuration.get_database_session()
		self.instance_type = self.session.query(
			paasmaker.model.ApplicationInstanceType
		).get(context['application_instance_type_id'])

		# Find all instances that need to be registered.
		# Attempt to grab all the data at once that is required.
		to_allocate = self.session.query(
			paasmaker.model.ApplicationInstance
		).options(
			sqlalchemy.orm.joinedload(
				paasmaker.model.ApplicationInstance.node
			)
		).filter(
			paasmaker.model.ApplicationInstance.application_instance_type == self.instance_type,
			paasmaker.model.ApplicationInstance.state == constants.INSTANCE.ALLOCATED
		)

		# Fetch out the root job ID for convenience.
		self.root_job_id = self.job_metadata['root_id']

		# And for each of those, create the following jobs:
		# - Store port
		#   - Register instance.
		self.instance_list = []
		for instance in to_allocate:
			self.instance_list.append(instance)
		self.instance_list.reverse()

		self.logger.info("Found %d instance that need to be registered.", len(self.instance_list))

		if len(self.instance_list) == 0:
			self.logger.info("No instances to register.")
			self.success({}, "No instances to register.")
		else:
			# Start creating jobs.
			self.create_job(self.instance_list.pop())

	def create_job(self, instance):
		self.logger.info("Creating registration job on node %s.", instance.node.name)
		def on_register_job(register_job_id):
			self.logger.info("Finished creating registration job on node %s.", instance.node.name)
			# Hook up the next job.
			try:
				self.create_job(self.instance_list.pop())
			except IndexError, ex:
				# No more instances!
				self.all_jobs_added()

		def on_storeport_job(storeport_job_id):
			# Now, add a child job that is to register the instance.
			self.configuration.job_manager.add_job(
				'paasmaker.job.heart.registerinstance',
				instance.flatten_for_heart(),
				'Register instance %s on node %s' % (instance.instance_id, instance.node.name),
				parent=storeport_job_id,
				callback=on_register_job,
				node=instance.node.uuid
			)

		# Add the first job for the instance.
		self.configuration.job_manager.add_job(
			'paasmaker.job.coordinate.storeport',
			{
				'instance_id': instance.instance_id,
				'database_id': instance.id
			},
			'Store instance port',
			parent=self.root_job_id,
			callback=on_storeport_job
		)

	def all_jobs_added(self):
		self.logger.info("Kicking off registration jobs.")
		# Now, make them all executable and start the process.
		self.configuration.job_manager.allow_execution(self.root_job_id, callback=self.all_executable)

	def all_executable(self):
		self.logger.info("Completed kicking off registration jobs.")
		self.success({}, "Set up all registration jobs.")
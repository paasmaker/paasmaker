
import uuid

import paasmaker
from paasmaker.common.core import constants
from ..base import BaseJob
from paasmaker.util.plugin import MODE

import tornado
from pubsub import pub
import sqlalchemy

import colander

class RegisterRequestJobParametersSchema(colander.MappingSchema):
	application_instance_type_id = colander.SchemaNode(colander.Integer())

class RegisterRequestJob(BaseJob):
	MODES = {
		MODE.JOB: RegisterRequestJobParametersSchema()
	}

	def start_job(self, context):
		self.logger.info("Creating node registration jobs.")

		session = self.configuration.get_database_session()
		instance_type = session.query(
			paasmaker.model.ApplicationInstanceType
		).get(self.parameters['application_instance_type_id'])

		# Find all instances that need to be registered.
		# Attempt to grab all the data at once that is required.
		to_allocate = session.query(
			paasmaker.model.ApplicationInstance
		).options(
			sqlalchemy.orm.joinedload(
				paasmaker.model.ApplicationInstance.node
			)
		).filter(
			paasmaker.model.ApplicationInstance.application_instance_type == instance_type,
			paasmaker.model.ApplicationInstance.state == constants.INSTANCE.ALLOCATED
		)

		# Now set up the jobs.
		container = self.configuration.job_manager.get_specifier()
		container.set_job(
			'paasmaker.job.container',
			{},
			'Register container for %s' % instance_type.name
		)

		self.logger.info("Found %d instance that need to be registered.", to_allocate.count())

		# And for each of those, create the following jobs:
		# - Store port
		#   - Register instance.
		self.instance_list = []
		for instance in to_allocate:
			storeport = container.add_child()
			storeport.set_job(
				'paasmaker.job.coordinate.storeport',
				{
					'instance_id': instance.instance_id,
					'database_id': instance.id
				},
				'Store instance port'
			)

			register = storeport.add_child()
			register.set_job(
				'paasmaker.job.heart.registerinstance',
				instance.flatten_for_heart(),
				'Register instance %s on node %s' % (instance.instance_id, instance.node.name),
				node=instance.node.uuid
			)

		def on_tree_executable():
			self.success({}, "Created all registration jobs.")

		def on_tree_added(root_id):
			self.configuration.job_manager.allow_execution(self.job_metadata['root_id'], callback=on_tree_executable)

		# Add that entire tree into the job manager.
		self.configuration.job_manager.add_tree(container, on_tree_added, parent=self.job_metadata['root_id'])
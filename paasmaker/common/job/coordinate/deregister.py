
import os
import subprocess
import uuid

import paasmaker
from paasmaker.common.core import constants
from ...testhelpers import TestHelpers
from instancerootbase import InstanceRootBase
from instancejobhelper import InstanceJobHelper
from paasmaker.util.plugin import MODE

import tornado
from pubsub import pub
import colander

# TODO: Implement abort features for all of these jobs.

# - Root
#   - Deregister Requester - queues up other jobs.
#   - Deregister - Instance A
#   - Deregister - Instance B

class DeRegisterRootJob(InstanceRootBase):
	@staticmethod
	def setup_version(configuration, application_version, callback):
		# List all the instance types.
		# Assume we have an open session on the application_version object.

		context = {}
		context['application_version_id'] = application_version.id

		tags = []
		tags.append('workspace:%d' % application_version.application.workspace.id)
		tags.append('application:%d' % application_version.application.id)
		tags.append('application_version:%d' % application_version.id)

		# The root of this tree.
		tree = configuration.job_manager.get_specifier()
		tree.set_job(
			'paasmaker.job.coordinate.deregisterroot',
			{},
			"Deregister instances on nodes for %s version %d" % (application_version.application.name, application_version.version),
			context=context,
			tags=tags
		)

		for instance_type in application_version.instance_types:
			parameters = {}
			parameters['application_instance_type_id'] = instance_type.id

			# The tag gets added here, but it's actually tagged on the root job.
			type_tags = ['application_instance_type:%d' % instance_type.id]

			registerer = tree.add_child()
			registerer.set_job(
				'paasmaker.job.coordinate.deregisterrequest',
				parameters,
				"Deregister requests",
				tags=type_tags
			)

		def on_tree_added(root_id):
			callback(root_id)

		configuration.job_manager.add_tree(tree, on_tree_added)

	def start_job(self, context):
		self.update_jobs_from_context(context)
		self.update_version_from_context(context, constants.VERSION.PREPARED)

		self.logger.info("Deregister instances.")
		self.success({}, "Deregistered instances.")

class DeRegisterRequestJobParametersSchema(colander.MappingSchema):
	application_instance_type_id = colander.SchemaNode(colander.Integer())

class DeRegisterRequestJob(InstanceJobHelper):
	MODES = {
		MODE.JOB: DeRegisterRequestJobParametersSchema()
	}

	def start_job(self, context):
		# We've been supplied with an instance type, so now locate all instances for
		# that type, and queue jobs for them.
		session = self.configuration.get_database_session()

		instance_type = self.get_instance_type(session)
		instances = self.get_instances(
			session,
			instance_type,
			[constants.INSTANCE.STOPPED, constants.INSTANCE.ERROR]
		)

		tags = self.get_tags_for(instance_type)

		# The root of this tree.
		container = self.configuration.job_manager.get_specifier()
		container.set_job(
			'paasmaker.job.container',
			{},
			'Shutdown container for %s' % instance_type.name,
			tags=tags
		)

		for instance in instances:
			deregistration = container.add_child()
			deregistration.set_job(
				'paasmaker.job.heart.deregisterinstance',
				{
					'instance_id': instance.instance_id
				},
				"Deregister instance %s on node %s" % (instance.instance_id, instance.node.name),
				node=instance.node.uuid
			)

		def on_tree_executable():
			self.success({}, "Created all de registration jobs.")

		def on_tree_added(root_id):
			self.configuration.job_manager.allow_execution(self.job_metadata['root_id'], callback=on_tree_executable)

		# Add that entire tree into the job manager.
		self.configuration.job_manager.add_tree(container, on_tree_added, parent=self.job_metadata['root_id'])

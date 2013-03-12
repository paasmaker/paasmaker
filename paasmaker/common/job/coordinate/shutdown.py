
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
#   - Shutdown Requester - queues up other jobs.
#   - Shutdown - Instance A
#     - Update Routing - Instance A
#   - Shutdown - Instance B
#     - Update Routing - Instance B

class ShutdownRootJob(InstanceRootBase):
	"""
	A container job to submit other jobs to shutdown an application version.
	"""
	@classmethod
	def setup_version(cls, configuration, application_version, callback, error_callback, limit_instances=None, parent=None):
		# List all the instance types.
		# Assume we have an open session on the application_version object.

		context = {}
		context['application_version_id'] = application_version.id

		if limit_instances:
			context['limit_instances'] = limit_instances

		tags = []
		tags.append('workspace:%d' % application_version.application.workspace.id)
		tags.append('application:%d' % application_version.application.id)
		tags.append('application_version:%d' % application_version.id)

		# The root of this tree.
		tree = configuration.job_manager.get_specifier()
		tree.set_job(
			'paasmaker.job.coordinate.shutdownroot',
			{},
			"Shutdown up instances and alter routing for %s version %d" % (application_version.application.name, application_version.version),
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
				'paasmaker.job.coordinate.shutdownrequest',
				parameters,
				"Shutdown requests for %s" % instance_type.name,
				tags=type_tags
			)

		def on_tree_added(root_id):
			callback(root_id)

		configuration.job_manager.add_tree(tree, on_tree_added, parent=parent)

	def start_job(self, context):
		def version_updated():
			self.logger.info("Shutdown instances and alter routing.")
			self.success({}, "Shut down instances and altered routing.")

		def jobs_updated():
			self.update_version_from_context(context, constants.VERSION.READY, version_updated)

		self.update_jobs_from_context(context, jobs_updated)

class ShutdownRequestJobParametersSchema(colander.MappingSchema):
	application_instance_type_id = colander.SchemaNode(colander.Integer())

class ShutdownRequestJob(InstanceJobHelper):
	"""
	A job to submit shutdown requests on specific heart nodes to shutdown instances.
	"""
	MODES = {
		MODE.JOB: ShutdownRequestJobParametersSchema()
	}

	def start_job(self, context):
		# We've been supplied with an instance type, so now locate all instances for
		# that type, and queue jobs for them.
		def got_session(session):
			instance_type = self.get_instance_type(session)
			instances = self.get_instances(
				session,
				instance_type,
				[constants.INSTANCE.RUNNING, constants.INSTANCE.STARTING],
				context
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
				shutdown = container.add_child()
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

			def on_tree_executable():
				self.success({}, "Created all shutdown jobs.")

			def on_tree_added(root_id):
				self.configuration.job_manager.allow_execution(self.job_metadata['root_id'], callback=on_tree_executable)

			# Add that entire tree into the job manager.
			session.close()
			self.configuration.job_manager.add_tree(container, on_tree_added, parent=self.job_metadata['root_id'])

			# end of got_session()

		self.configuration.get_database_session(got_session, self._failure_callback)

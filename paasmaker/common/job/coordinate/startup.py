
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
#   - Startup Requester - queues up other jobs.
#   - Routing - Instance A
#     - Startup - Instance A
#       - Pre-startup - Instance A
#   - Routing - Instance B
#     - Startup - Instance B
#       - Pre-startup - Instance B

class StartupRootJob(InstanceRootBase):
	@classmethod
	def setup_version(cls, configuration, application_version, callback, limit_instances=None):
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
			'paasmaker.job.coordinate.startuproot',
			{},
			"Start up instances and alter routing for %s version %d" % (application_version.application.name, application_version.version),
			context=context,
			tags=tags
		)

		for instance_type in application_version.instance_types:
			# Don't start up exclusive instance types here, unless
			# this version is current.
			exclusive = instance_type.exclusive
			current = application_version.is_current

			if not exclusive or current:
				parameters = {}
				parameters['application_instance_type_id'] = instance_type.id

				# The tag gets added here, but it's actually tagged on the root job.
				type_tags = ['application_instance_type:%d' % instance_type.id]

				registerer = tree.add_child()
				registerer.set_job(
					'paasmaker.job.coordinate.startuprequest',
					parameters,
					"Startup requests for %s" % instance_type.name,
					tags=type_tags
				)

		def on_tree_added(root_id):
			callback(root_id)

		configuration.job_manager.add_tree(tree, on_tree_added)

	def start_job(self, context):
		self.update_jobs_from_context(context)
		self.update_version_from_context(context, constants.VERSION.RUNNING)

		self.logger.info("Startup instances and alter routing.")
		self.success({}, "Started up instances and altered routing.")

class StartupRequestJobParametersSchema(colander.MappingSchema):
	application_instance_type_id = colander.SchemaNode(colander.Integer())

class StartupRequestJob(InstanceJobHelper):
	MODES = {
		MODE.JOB: StartupRequestJobParametersSchema()
	}

	def start_job(self, context):
		# We've been supplied with an instance type, so now locate all instances for
		# that type, and queue jobs for them.
		session = self.configuration.get_database_session()

		instance_type = self.get_instance_type(session)
		instances = self.get_instances(
			session,
			instance_type,
			constants.INSTANCE_CAN_START_STATES,
			context
		)

		tags = self.get_tags_for(instance_type)

		# The root of this tree.
		container = self.configuration.job_manager.get_specifier()
		container.set_job(
			'paasmaker.job.container',
			{},
			'Startup container for %s' % instance_type.name,
			tags=tags
		)

		for instance in instances:
			routing = container.add_child()
			routing.set_job(
				'paasmaker.job.routing.update',
				{
					'instance_id': instance.id,
					'add': True
				},
				"Update routing for %s" % instance.instance_id
			)

			startup = routing.add_child()
			startup.set_job(
				'paasmaker.job.heart.startup',
				{
					'instance_id': instance.instance_id
				},
				"Startup instance %s on node %s" % (instance.instance_id, instance.node.name),
				node=instance.node.uuid
			)

			prestartup = startup.add_child()
			prestartup.set_job(
				'paasmaker.job.heart.prestartup',
				{
					'instance_id': instance.instance_id
				},
				"Pre startup instance %s on node %s" % (instance.instance_id, instance.node.name),
				node=instance.node.uuid
			)

		def on_tree_executable():
			self.success({}, "Created all startup jobs.")

		def on_tree_added(root_id):
			self.configuration.job_manager.allow_execution(self.job_metadata['root_id'], callback=on_tree_executable)

		# Add that entire tree into the job manager.
		self.configuration.job_manager.add_tree(container, on_tree_added, parent=self.job_metadata['root_id'])

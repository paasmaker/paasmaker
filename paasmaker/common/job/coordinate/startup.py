#
# Paasmaker - Platform as a Service
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#

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
#   - Startup Requester - queues up other jobs (will be children of root)
#     - Register Request - queues up other jobs (will be children of startup requester)
#       - Select locations
#   - Routing - Instance A
#     - Startup - Instance A
#       - Pre-startup - Instance A
#   - Routing - Instance B
#     - Startup - Instance B
#       - Pre-startup - Instance B

class StartupRootJob(InstanceRootBase):
	"""
	A container job to submit more jobs to start up instances for a given application version.
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

				starter = tree.add_child()
				starter.set_job(
					'paasmaker.job.coordinate.startuprequest',
					parameters,
					"Startup requests for %s" % instance_type.name,
					tags=type_tags
				)

				registerer = starter.add_child()
				registerer.set_job(
					'paasmaker.job.coordinate.registerrequest',
					parameters,
					"Registration requests for %s" % instance_type.name,
					tags=type_tags
				)

				selectlocations = registerer.add_child()
				selectlocations.set_job(
					'paasmaker.job.coordinate.selectlocations',
					parameters,
					"Select instance locations for %s" % instance_type.name,
				)

		def on_tree_added(root_id):
			callback(root_id)

		configuration.job_manager.add_tree(tree, on_tree_added, parent=parent)

	def start_job(self, context):
		def version_updated():
			self.logger.info("Startup instances and alter routing.")
			self.success({}, "Started up instances and altered routing.")

		def jobs_updated():
			self.update_version_from_context(context, constants.VERSION.RUNNING, version_updated)

		self.update_jobs_from_context(context, jobs_updated)

class StartupRequestJobParametersSchema(colander.MappingSchema):
	application_instance_type_id = colander.SchemaNode(colander.Integer())

class StartupRequestJob(InstanceJobHelper):
	"""
	A job to submit more jobs to start an instance on a specific heart node.
	"""
	MODES = {
		MODE.JOB: StartupRequestJobParametersSchema()
	}

	def start_job(self, context):
		# We've been supplied with an instance type, so now locate all instances for
		# that type, and queue jobs for them.
		def got_session(session):
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
			session.close()
			self.configuration.job_manager.add_tree(container, on_tree_added, parent=self.job_metadata['parent_id'])

			# end of got_session()

		self.configuration.get_database_session(got_session, self._failure_callback)
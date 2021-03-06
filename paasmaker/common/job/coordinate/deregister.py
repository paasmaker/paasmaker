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
#   - Deregister Requester - queues up other jobs.
#   - Deregister - Instance A
#   - Deregister - Instance B

class DeRegisterRootJob(InstanceRootBase):
	"""
	A job to set up de-registration request jobs.

	NOTE: All this job does is submit more jobs to de-register instances.
	"""

	@classmethod
	def setup_version(cls, configuration, application_version, callback, error_callback, limit_instances=None, parent=None):
		# List all the instance types.
		# Assume we have an open session on the application_version object.

		context = {}
		context['application_version_id'] = application_version.id

		context['update_version'] = True
		if limit_instances:
			context['limit_instances'] = limit_instances

			# If we're shutting down just some instances, don't update
			# the version to READY. Why? Because when we're adjusting
			# just some instances it's normally for a health check of some kind,
			# so we still want the version to be running.
			# TODO: This is an assumption and an edge case.
			context['update_version'] = False

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
				"Deregister request creator for %s" % instance_type.name,
				tags=type_tags
			)

		def on_tree_added(root_id):
			callback(root_id)

		configuration.job_manager.add_tree(tree, on_tree_added, parent=parent)

	def start_job(self, context):
		def version_updated():
			self.logger.info("Deregister instances.")
			self.success({}, "Deregistered instances.")

		def jobs_updated():
			self.update_version_from_context(context, constants.VERSION.PREPARED, version_updated)

		self.update_jobs_from_context(context, jobs_updated)

class DeRegisterRequestJobParametersSchema(colander.MappingSchema):
	application_instance_type_id = colander.SchemaNode(colander.Integer())

class DeRegisterRequestJob(InstanceJobHelper):
	"""
	A job that queues deregistration jobs for a specific instance type ID.

	This queues the actual jobs that run on the heart nodes to perform the deregistration.
	"""
	MODES = {
		MODE.JOB: DeRegisterRequestJobParametersSchema()
	}

	def start_job(self, context):
		def got_session(session):
			# We've been supplied with an instance type, so now locate all instances for
			# that type, and queue jobs for them.

			instance_type = self.get_instance_type(session)
			instances = self.get_instances(
				session,
				instance_type,
				[
					constants.INSTANCE.ALLOCATED,
					constants.INSTANCE.REGISTERED,
					constants.INSTANCE.STOPPED,
					constants.INSTANCE.ERROR
				],
				context
			)

			tags = self.get_tags_for(instance_type)

			# The root of this tree.
			container = self.configuration.job_manager.get_specifier()
			container.set_job(
				'paasmaker.job.container',
				{},
				'Deregister container for %s' % instance_type.name,
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
			session.close()
			self.configuration.job_manager.add_tree(container, on_tree_added, parent=self.job_metadata['root_id'])

		self.configuration.get_database_session(got_session, self._failure_callback)

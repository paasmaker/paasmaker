#
# Paasmaker - Platform as a Service
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#

import time
import gzip
import json
import shutil
import os
import datetime

import paasmaker
from base import BasePeriodic, BasePeriodicTest
from ..testhelpers import TestHelpers

import colander

class OldInstancesConfigurationSchema(colander.MappingSchema):
	max_age = colander.SchemaNode(
		colander.Integer(),
		title="Maximum age",
		description="Maximum age for instances in this state. In seconds.",
		default=3600 * 24,
		missing=3600 * 24
	)
	states = colander.SchemaNode(
		colander.Set(),
		title="States to remove",
		description="A set of states to remove after the timeout.",
		default=[],
		missing=[]
	)
	only_inactive = colander.SchemaNode(
		colander.Boolean(),
		title="Only Inactive Versions",
		description="Only operate on inactive versions of an application.",
		default=True,
		missing=True
	)

class OldInstancesCleaner(BasePeriodic):
	"""
	A plugin to remove inactive instances from the system, after a timeout.
	"""

	OPTIONS_SCHEMA = OldInstancesConfigurationSchema()
	API_VERSION = "0.9.0"

	def on_interval(self, callback, error_callback):
		if not self.configuration.is_pacemaker():
			callback("Not a pacemaker, so not removing old instances.")
			return

		self.callback = callback
		self.error_callback = error_callback

		if len(self.options['states']) == 0:
			message = "No states configured for this plugin. Not taking any action."
			self.logger.warning(message)
			callback(message)
			return

		self.configuration.get_database_session(self._got_database_session, error_callback)

	def _got_database_session(self, session):
		self.session = session
		# Find instances that match.
		older_than = datetime.datetime.now() - datetime.timedelta(seconds=self.options['max_age'])
		instances_to_clean = self.session.query(
			paasmaker.model.ApplicationInstance
		).filter(
			paasmaker.model.ApplicationInstance.state.in_(self.options['states']),
			paasmaker.model.ApplicationInstance.updated < older_than
		)

		if self.options['only_inactive']:
			# Can't easily query the version state backwards, so we need
			# some subqueries to find it.

			# First, all inactive versions.
			inactive_versions = self.session.query(
				paasmaker.model.ApplicationVersion.id
			).filter(
				paasmaker.model.ApplicationVersion.is_current == False
			)

			# Then, inactive instance types based on those versions.
			inactive_instance_types = self.session.query(
				paasmaker.model.ApplicationInstanceType.id
			).filter(
				paasmaker.model.ApplicationInstanceType.application_version_id.in_(inactive_versions)
			)

			# And finally, the instances. SQLAlchemy should send SQL to the remote end
			# which should be able to efficiently answer this query and return the results.
			# TODO: Test the scaling of this as it might block the process.
			instances_to_clean = instances_to_clean.filter(
				paasmaker.model.ApplicationInstance.application_instance_type_id.in_(inactive_instance_types)
			)

		pending_instances = instances_to_clean.all()
		found_instance_count = len(pending_instances)

		def error_adding_job(message, exception=None):
			self.session.close()
			self.logger.error("Error adding job.")
			self.logger.error(message)
			self.error_callback("Error adding job: " + message)

		def handle_instance(instance, processor):
			def job_executable():
				processor.next()

			def added_job(job_id):
				self.logger.info(
					"Added deregistration job for instance %s in state '%s'.",
					instance.instance_id,
					instance.state
				)
				self.configuration.job_manager.allow_execution(
					job_id,
					job_executable
				)
				# end of added_job()

			paasmaker.common.job.coordinate.DeRegisterRootJob.setup_version(
				self.configuration,
				instance.application_instance_type.application_version,
				added_job,
				error_adding_job,
				limit_instances=[instance.instance_id]
			)

			# end of handle_instance()

		def done_instances():
			self.session.close()
			message = "Completed adding jobs for %d instances." % found_instance_count
			self.logger.info(message)
			self.callback(message)

		processor = paasmaker.util.callbackprocesslist.CallbackProcessList(
			pending_instances,
			handle_instance,
			done_instances
		)
		processor.start()

class OldInstancesCleanerTest(BasePeriodicTest, TestHelpers):
	def setUp(self):
		super(OldInstancesCleanerTest, self).setUp()

		self.configuration.plugins.register(
			'paasmaker.periodic.oldinstances.error',
			'paasmaker.common.periodic.oldinstances.OldInstancesCleaner',
			{
				'states': ['ERROR'],
				'only_inactive': False,
				'max_age': -10
			},
			'Old Instances Cleanup Plugin'
		)

		self.configuration.plugins.register(
			'paasmaker.periodic.oldinstances.stopped',
			'paasmaker.common.periodic.oldinstances.OldInstancesCleaner',
			{
				'states': ['STOPPED'],
				'only_inactive': True,
				'max_age': -10
			},
			'Old Instances Cleanup Plugin'
		)

		self.configuration.startup_job_manager(self.stop, self.stop)
		self.wait()

	def tearDown(self):
		self.configuration.cleanup(self.stop, self.stop)
		try:
			self.wait()
		except paasmaker.thirdparty.tornadoredis.exceptions.ConnectionError, ex:
			# This is raised because we kill Redis and some things
			# are still pending. We can safely ignore it.
			pass

	def test_simple(self):
		self.configuration.get_database_session(self.stop, self.stop)
		session = self.wait()

		instance_type = self.create_sample_application(
			self.configuration,
			'paasmaker.runtime.shell',
			{},
			'1',
			'tornado-simple',
			session
		)
		node = self.add_simple_node(
			session,
			{},
			self.configuration
		)

		instance = self.create_sample_application_instance(
			self.configuration,
			session,
			instance_type,
			node
		)

		instance.state = paasmaker.common.core.constants.INSTANCE.ERROR
		session.add(instance)
		session.commit()

		plugin = self.configuration.plugins.instantiate(
			'paasmaker.periodic.oldinstances.error',
			paasmaker.util.plugin.MODE.PERIODIC
		)

		plugin.on_interval(self.success_callback, self.failure_callback)
		self.wait()

		self.assertTrue(self.success)
		self.assertIn(" 1 ", self.message, "Didn't find an instance to work on.")

		# Set the application to current, and try again. Should still
		# process a single instance.
		version = instance.application_instance_type.application_version
		version.make_current(session)

		plugin.on_interval(self.success_callback, self.failure_callback)
		self.wait()

		self.assertTrue(self.success)
		self.assertIn(" 1 ", self.message, "Didn't find an instance to work on.")

		# Set to stopped. Query should not find it.
		instance.state = paasmaker.common.core.constants.INSTANCE.STOPPED
		session.add(instance)
		session.commit()

		plugin.on_interval(self.success_callback, self.failure_callback)
		self.wait()

		self.assertTrue(self.success)
		self.assertIn(" 0 ", self.message, "Incorrectly found instance to work on.")

		# Now try a differently configured plugin.
		# It should not find the instance, as it's the current version.
		plugin = self.configuration.plugins.instantiate(
			'paasmaker.periodic.oldinstances.stopped',
			paasmaker.util.plugin.MODE.PERIODIC
		)

		plugin.on_interval(self.success_callback, self.failure_callback)
		self.wait()

		self.assertTrue(self.success)
		self.assertIn(" 0 ", self.message, "Found instance when it should not have.")

		# Make the version not-current anymore.
		# There is no "unmake current" so we manually unset the flag here.
		version.is_current = False
		session.add(version)
		session.commit()

		# Now the same check should find a single instance.
		plugin.on_interval(self.success_callback, self.failure_callback)
		self.wait()

		self.assertTrue(self.success)
		self.assertIn(" 1 ", self.message, "Didn't find stopped instance.")
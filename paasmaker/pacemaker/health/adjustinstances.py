
import uuid
import datetime

import paasmaker
from paasmaker.common.core import constants

from base import BaseHealthCheck, BaseHealthCheckTest

import colander

class AdjustInstancesHealthCheckParametersSchema(colander.MappingSchema):
	startup_wait = colander.SchemaNode(colander.Integer(),
		title="Startup Delay",
		description="The number of seconds after an application is RUNNING to start adjusting instances.",
		default=20,
		missing=20)

class AdjustInstancesHealthCheck(BaseHealthCheck):
	MODES = {
		paasmaker.util.plugin.MODE.HEALTH_CHECK: AdjustInstancesHealthCheckParametersSchema(),
	}
	API_VERSION = "0.9.0"

	def check(self, parent_job_id, callback, error_callback):
		self.session = self.configuration.get_database_session()
		self.callback = callback
		self.error_callback = error_callback
		self.parent_job_id = parent_job_id

		# Find applications in state RUNNING, and check their instances.
		# Only check applications that haven't been altered for
		# a short time; this stops race conditions around normal startup
		# conditions.
		older_than = datetime.datetime.utcnow() - datetime.timedelta(0, self.parameters['startup_wait'])

		self.running_versions = self.session.query(
			paasmaker.model.ApplicationVersion
		).filter(
			paasmaker.model.ApplicationVersion.state == constants.VERSION.RUNNING,
			paasmaker.model.ApplicationVersion.updated < older_than
		).all()

		self.active_nodes = self.session.query(
			paasmaker.model.Node.id
		).filter(
			paasmaker.model.Node.state == constants.NODE.ACTIVE
		)

		self.checked_version_count = len(self.running_versions)
		self.stop_actions = 0
		self.start_actions = 0
		self.stopped_instances = 0
		self.whole_start_version = None

		self.logger.info("Checking %d running versions.", self.checked_version_count)

		# Start processing them on the IO loop, so as to coordinate with
		# other things that the system is doing.
		self.configuration.io_loop.add_callback(self._get_next_version)

	def _get_next_version(self):
		if self.whole_start_version:
			# Need to kick off a start action for an entire
			# version. Do that now, and then move on.
			def submitted(job_id):
				self.whole_start_version = None
				self.start_actions += 1
				self._get_next_version()

			paasmaker.common.job.coordinate.startup.StartupRootJob.setup_version(
				self.configuration,
				self.whole_start_version,
				submitted,
				parent=self.parent_job_id
			)
		else:
			try:
				version = self.running_versions.pop()
				self.whole_start_version = None

				self._check_version(version)

			except IndexError, ex:
				# No more to process.
				self._finish()

	def _check_version(self, version):
		self.instance_types = self.session.query(
			paasmaker.model.ApplicationInstanceType
		).filter(
			paasmaker.model.ApplicationInstanceType.application_version == version
		).all()
		self._get_next_instance_type()

	def _get_next_instance_type(self):
		try:
			instance_type = self.instance_types.pop()

			self._check_instance_type(instance_type)

		except IndexError, ex:
			# No more to process.
			self.configuration.io_loop.add_callback(self._get_next_version)

	def _check_instance_type(self, instance_type):
		# Find how many are running only. Because this is obviously our
		# target state.
		adjustment_quantity = instance_type.adjustment_instances(
			self.session,
			states=[constants.INSTANCE.RUNNING]
		)

		self.logger.info(
			"%s, version %d, type %s, adjustment required: %d.",
			instance_type.application_version.application.name,
			instance_type.application_version.version,
			instance_type.name,
			adjustment_quantity
		)

		if adjustment_quantity == 0:
			# No action required.
			self.configuration.io_loop.add_callback(self._get_next_instance_type)

		elif adjustment_quantity > 0:
			# We need more instances.
			# If we perform the start job, it will assign and allocate more instances
			# as needed. But the start job only works against an entire version...
			# Mark it as needing to start. Another part will pick it up.
			self.whole_start_version = instance_type.application_version
			self.configuration.io_loop.add_callback(self._get_next_instance_type)

		elif adjustment_quantity < 0:
			# We need less instances.
			# Don't deregister them at this stage, just stop them.
			# TODO: Probably should de-register the instances. Or another
			# health check comes along to do that for us?

			# Fetch all the instances, and then rank them.
			instances = self.session.query(
				paasmaker.model.ApplicationInstance
			).filter(
				paasmaker.model.ApplicationInstance.application_instance_type_id == instance_type.id,
				paasmaker.model.ApplicationInstance.node_id.in_(self.active_nodes)
			).all()

			def rank_by_node(a, b):
				return int((a.node.score * 100) - (b.node.score * 100))

			instances = sorted(instances, cmp=rank_by_node)

			# Now extract the worst instances to stop.
			instances = instances[adjustment_quantity:]

			self.stop_actions += 1
			self.stopped_instances += len(instances)

			paasmaker.common.job.coordinate.shutdown.ShutdownRootJob.setup_instances(
				self.configuration,
				instances,
				self._instance_type_job_submitted,
				parent=self.parent_job_id
			)

	def _instance_type_job_submitted(self, job_id):
		self.logger.info("Added corrective job, root %s", job_id)
		self.configuration.io_loop.add_callback(self._get_next_instance_type)

	def _finish(self):
		# Make this job tree executable.
		def done_executable():
			self.session.close()
			self.callback(
				{
					'adjusted_checked_versions': self.checked_version_count,
					'adjusted_stop_actions': self.stop_actions,
					'adjusted_start_actions': self.start_actions,
					'adjusted_stopped_instances': self.stopped_instances
				},
				"Completed. %d versions checked, %d stop requests (%d instances), %d start requests." % (self.checked_version_count, self.stop_actions, self.stopped_instances, self.start_actions)
			)

		self.configuration.job_manager.allow_execution(self.parent_job_id, done_executable)

class AdjustInstancesHealthCheckTest(BaseHealthCheckTest):

	def setUp(self):
		super(AdjustInstancesHealthCheckTest, self).setUp()

		self.registry.register(
			'paasmaker.health.adjustinstances',
			'paasmaker.pacemaker.health.adjustinstances.AdjustInstancesHealthCheck',
			{},
			'Adjust Instances health check'
		)

	def test_standard(self):
		session = self.configuration.get_database_session()

		health = self.registry.instantiate(
			'paasmaker.health.adjustinstances',
			paasmaker.util.plugin.MODE.HEALTH_CHECK,
			{}
		)

		# Now create a node that should remain up.
		up_uuid = str(uuid.uuid4())
		up_node = paasmaker.model.Node('test_up', 'localhost', 12346, up_uuid, constants.NODE.ACTIVE)
		session.add(up_node)
		session.commit()

		# Create a container job.
		self.configuration.job_manager.add_job('paasmaker.job.container', {}, "Example job.", self.stop)
		job_id = self.wait()

		# Now run the check, and see what happened.
		health.check(
			job_id,
			self.success_callback,
			self.failure_callback
		)

		self.wait()

		# It shouldn't have done anything, but should have succeeded at doing nothing.
		self.assertTrue(self.success, "Should have succeeded.")
		self.assertEquals(self.context['adjusted_checked_versions'], 0, "Should not have checked any versions.")

		# Create a sample application with a few instances.
		instance_type = self.create_sample_application(
			self.configuration,
			'paasmaker.runtime.shell',
			{},
			'1',
			'tornado-simple'
		)

		instance_type = session.query(
			paasmaker.model.ApplicationInstanceType
		).get(instance_type.id)

		instance_running = self.create_sample_application_instance(
			self.configuration,
			session,
			instance_type,
			up_node
		)

		instance_running.state = constants.INSTANCE.RUNNING
		session.add(instance_running)
		session.commit()

		version = session.query(
			paasmaker.model.ApplicationVersion
		).get(instance_type.application_version_id)

		version.state = constants.VERSION.RUNNING
		session.add(version)
		session.commit()

		# Recreate the plugin, and make it look into the future.
		health = self.registry.instantiate(
			'paasmaker.health.adjustinstances',
			paasmaker.util.plugin.MODE.HEALTH_CHECK,
			{'startup_wait': -20}
		)

		# Run the health check. We only need one instance, so it should succeed with
		# no start/shutdown requests.
		health.check(
			job_id,
			self.success_callback,
			self.failure_callback
		)

		self.wait()

		# It shouldn't have done anything, but should have succeeded at doing nothing.
		self.assertTrue(self.success, "Should have succeeded.")
		self.assertEquals(self.context['adjusted_checked_versions'], 1, "Didn't check any versions.")
		self.assertEquals(self.context['adjusted_stop_actions'], 0, "Performed stop actions.")
		self.assertEquals(self.context['adjusted_start_actions'], 0, "Performed start actions.")

		# Stop that instance, and run again.
		instance_running.state = constants.INSTANCE.STOPPED
		session.add(instance_running)
		session.commit()

		health.check(
			job_id,
			self.success_callback,
			self.failure_callback
		)

		self.wait()

		self.assertTrue(self.success, "Should have succeeded.")
		self.assertEquals(self.context['adjusted_checked_versions'], 1, "Didn't check any versions.")
		self.assertEquals(self.context['adjusted_stop_actions'], 0, "Performed stop actions.")
		self.assertEquals(self.context['adjusted_start_actions'], 1, "Didn't perform start actions.")

		# Update it again to running.
		# And then add another instance, which will be too many.
		instance_running.state = constants.INSTANCE.RUNNING
		session.add(instance_running)
		session.commit()

		instance_extra = self.create_sample_application_instance(
			self.configuration,
			session,
			instance_type,
			up_node
		)

		instance_extra.state = constants.INSTANCE.RUNNING
		session.add(instance_extra)
		session.commit()

		health.check(
			job_id,
			self.success_callback,
			self.failure_callback
		)

		self.wait()

		self.assertTrue(self.success, "Should have succeeded.")
		self.assertEquals(self.context['adjusted_checked_versions'], 1, "Didn't check any versions.")
		self.assertEquals(self.context['adjusted_stop_actions'], 1, "Didn't perform stop actions.")
		self.assertEquals(self.context['adjusted_stopped_instances'], 1, "Didn't stop instances.")
		self.assertEquals(self.context['adjusted_start_actions'], 0, "Performed start actions.")
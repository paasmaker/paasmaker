
import paasmaker

from ..base import BaseJob

class InstanceRootBase(BaseJob):
	"""
	A superclass that provides helpers for coordinate jobs that spawn off
	other jobs. This contains common functionality that was being
	duplicated between the jobs.
	"""

	@classmethod
	def setup_instances(cls, configuration, instances, callback, parent=None):
		"""
		For the given list of instances, look up the application versions,
		and then call ``setup_version`` for each of those, limiting their actions
		to just those instances supplied.

		:arg Configuration configuration: The configuration object.
		:arg list instances: A list of ApplicationInstance objects.
		:arg callable callback: The callback called once done.
		:arg str parent: The parent ID of all the jobs, or None if this is a new
			top level job.
		"""
		# Sanity check: Pass at least one instance object.
		if len(instances) == 0:
			raise ValueError("You must pass at least one instance object.")

		# Sanity check: make sure all the instances
		# are the same application instance type.
		last_id = instances[0].application_instance_type_id
		instance_id_list = []
		for instance in instances:
			if instance.application_instance_type_id != last_id:
				raise ValueError("Not all passed instances belong to the same instance type.")
			instance_id_list.append(instance.instance_id)

		version = instances[0].application_instance_type.application_version

		# Now that we've done that, call setup_version.
		cls.setup_version(configuration, version, callback, limit_instances=instance_id_list, parent=parent)

	def update_jobs_from_context(self, context):
		"""
		From the context, attempt to locate any keys that are instance ids,
		and update those to the states given by the values.
		"""
		session = self.configuration.get_database_session()
		for key, value in context.iteritems():
			# TODO: This is a very poor method of figuring out if the
			# key is an instance ID.
			# TODO: Optimise this somewhat. Should be possible with a single update.
			if key.startswith('state-'):
				instance_id = key[6:]
				instance = session.query(
					paasmaker.model.ApplicationInstance
				).filter(
					paasmaker.model.ApplicationInstance.instance_id == instance_id
				).first()

				if instance:
					# Update the instance state.
					self.logger.debug("Updating state for instance %s to %s", instance_id, value)
					instance.state = value
					session.add(instance)
		session.commit()

	def update_version_from_context(self, context, state):
		"""
		From the context, if a version is specified, update that
		version into the given state.
		"""
		if context.has_key('application_version_id'):
			# Update that application version ID to the prepared state,
			# because we've just applied this to the whole version.
			session = self.configuration.get_database_session()
			version = session.query(paasmaker.model.ApplicationVersion).get(context['application_version_id'])
			version.state = state
			session.add(version)
			session.commit()
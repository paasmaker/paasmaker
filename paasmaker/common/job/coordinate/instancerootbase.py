
import paasmaker

from ..base import BaseJob

class InstanceRootBase(BaseJob):
	def get_instance_type(self, session):
		instance_type = session.query(
			paasmaker.model.ApplicatioNInstanceType
		).get(self.parameters['application_instance_type_id'])

		return instance_type

	def get_instances(self, configuration, instance_type_id, states, instances=[]):
		"""
		Find instances for the given application, in the given state,
		and return a destroyable list of instances for queueing.
		"""
		# TODO: limit to the given list of instance IDs.
		session = configuration.get_database_session()
		instance_type = session.query(paasmaker.model.ApplicationInstanceType).get(instance_type_id)
		instances = session.query(
			paasmaker.model.ApplicationInstance
		).filter(
			paasmaker.model.ApplicationInstance.application_instance_type == instance_type,
			paasmaker.model.ApplicationInstance.state.in_(states)
		)
		instance_list = []
		for instance in instances:
			instance_list.append(
				{
					'id': instance.id,
					'instance_id': instance.instance_id,
					'node_name': instance.node.name,
					'node_uuid': instance.node.uuid
				}
			)
		instance_list.reverse()

		return instance_list

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
			if key.find('-') != -1:
				instance = session.query(
					paasmaker.model.ApplicationInstance
				).filter(
					paasmaker.model.ApplicationInstance.instance_id == key
				).first()

				if instance:
					# Update the instance state.
					self.logger.debug("Updating state for instance %s to %s", key, value)
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

import paasmaker

class InstanceRootBase(object):
	@staticmethod
	def get_instances_for(configuration, instance_type_id, states, instances=[]):
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
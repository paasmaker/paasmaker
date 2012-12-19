
import paasmaker

from ..base import BaseJob

class InstanceJobHelper(BaseJob):
	def get_instance_type(self, session):
		instance_type = session.query(
			paasmaker.model.ApplicationInstanceType
		).get(self.parameters['application_instance_type_id'])

		return instance_type

	def get_instances(self, session, instance_type, states, instances=[]):
		"""
		Find instances for the given application, in the given state,
		and return a destroyable list of instances for queueing.
		"""
		# TODO: limit to the given list of instance IDs.
		# This allows partials or targetting specific instances.
		self.logger.info("Looking for instances in states %s", str(states))
		instances = session.query(
			paasmaker.model.ApplicationInstance
		).filter(
			paasmaker.model.ApplicationInstance.application_instance_type == instance_type,
			paasmaker.model.ApplicationInstance.state.in_(states)
		)

		return instances

	def get_tags_for(self, instance_type):
		"""
		Return a set of job tags for the given instance type ID.
		"""
		tags = []
		tags.append('workspace:%d' % instance_type.application_version.application.workspace.id)
		tags.append('application:%d' % instance_type.application_version.application.id)
		tags.append('application_version:%d' % instance_type.application_version.id)
		tags.append('application_instance_type:%d' % instance_type.id)

		return tags
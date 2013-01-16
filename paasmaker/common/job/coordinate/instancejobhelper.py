
import paasmaker
from paasmaker.common.core import constants

from ..base import BaseJob

class InstanceJobHelper(BaseJob):
	def get_instance_type(self, session):
		instance_type = session.query(
			paasmaker.model.ApplicationInstanceType
		).get(self.parameters['application_instance_type_id'])

		return instance_type

	def get_instances(self, session, instance_type, states, context):
		"""
		Find instances for the given application, in the given state,
		and return a destroyable list of instances for queueing.
		"""
		self.logger.info("Looking for instances in states %s, on active nodes.", str(states))

		active_nodes = session.query(
			paasmaker.model.Node.id
		).filter(
			paasmaker.model.Node.state == constants.NODE.ACTIVE
		)

		instances = session.query(
			paasmaker.model.ApplicationInstance
		).filter(
			paasmaker.model.ApplicationInstance.application_instance_type == instance_type,
			paasmaker.model.ApplicationInstance.state.in_(states),
			paasmaker.model.ApplicationInstance.node_id.in_(active_nodes)
		)

		if context.has_key('limit_instances'):
			# Limit the query to the given instance IDs.
			self.logger.info("Limiting to instances %s", str(context['limit_instances']))
			instances = instances.filter(
				paasmaker.model.ApplicationInstance.instance_id.in_(context['limit_instances'])
			)

		self.logger.info("Found %d instances.", instances.count())

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
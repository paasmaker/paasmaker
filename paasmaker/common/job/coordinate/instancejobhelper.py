
import paasmaker
from paasmaker.common.core import constants

from ..base import BaseJob

class InstanceJobHelper(BaseJob):
	"""
	A superclass for various coordinate jobs, that provides common helpers
	that those jobs use.
	"""

	def get_instance_type(self, session):
		"""
		From the supplied job parameters, fetch and hydrate the
		application instance type we are working on.

		:arg Session session: The SQLAlchemy session to work in.
		"""
		instance_type = session.query(
			paasmaker.model.ApplicationInstanceType
		).get(self.parameters['application_instance_type_id'])

		return instance_type

	def get_instances(self, session, instance_type, states, context):
		"""
		Find instances for the given application, in the given state,
		and return a destroyable list of instances for queueing.

		:arg Session session: The SQLAlchemy session to work in.
		:arg ApplicationInstnaceType instance_type: The instance type to fetch instances for.
		:arg list states: The states of instances to fetch.
		:arg dict context: The job's context, used to control the listing parameters.
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
		Return a set of job tags for the given instance type.

		:arg ApplicationInstanceType instance_type: The instance type
			to work on.
		"""
		tags = []
		tags.append('workspace:%d' % instance_type.application_version.application.workspace.id)
		tags.append('application:%d' % instance_type.application_version.application.id)
		tags.append('application_version:%d' % instance_type.application_version.id)
		tags.append('application_instance_type:%d' % instance_type.id)

		return tags

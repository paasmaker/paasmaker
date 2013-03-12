
import uuid

import paasmaker
from paasmaker.common.core import constants
from ..base import BaseJob
from paasmaker.util.plugin import MODE

import tornado
from pubsub import pub

import colander

class StorePortJobParametersSchema(colander.MappingSchema):
	instance_id = colander.SchemaNode(colander.String())
	database_id = colander.SchemaNode(colander.Integer())

class StorePortJob(BaseJob):
	"""
	A helper job to store the port that a heart allocated for an instance
	inside the pacemakers database.
	"""
	MODES = {
		MODE.JOB: StorePortJobParametersSchema()
	}

	def start_job(self, context):
		instance_id = self.parameters['instance_id']
		database_id = self.parameters['database_id']
		self.logger.info("Storing port for instance %s" % instance_id)

		# Now, context should have a key that is the instance
		# ID, with the value being the port number.
		# Store that, and also store that the instance is registered.
		# If it didn't send us back a port number, then it's a standalone
		# instance, meaning it has no port. So just record that it's registered.

		def got_session(session):
			instance = session.query(paasmaker.model.ApplicationInstance).get(self.parameters['database_id'])

			key = "port-%s" % instance_id
			if context.has_key(key):
				instance.port = context[key]
				self.logger.debug("Remote allocated port %d to this instance." % instance.port)
			else:
				self.logger.debug("Remote did not return a port for this instance.")

			instance.state = constants.INSTANCE.REGISTERED

			session.add(instance)
			session.commit()
			session.close()

			self.success({}, "Updated instance %s" % instance_id)

			# end of got_session()

		self.configuration.get_database_session(got_session, self._failure_callback)

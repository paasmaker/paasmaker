
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

		session = self.configuration.get_database_session()
		instance = session.query(paasmaker.model.ApplicationInstance).get(self.parameters['database_id'])

		if context.has_key(instance_id):
			instance.port = context[instance_id]
			self.logger.debug("Remote allocated port %d to this instance." % instance.port)
		else:
			self.logger.debug("Remote did not return a port for this instance.")

		instance.state = constants.INSTANCE.REGISTERED

		session.add(instance)
		session.commit()

		self.success({}, "Updated instance %s" % instance_id)

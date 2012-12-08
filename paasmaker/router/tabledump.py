import paasmaker

class RouterTableDump(object):
	def __init__(self, configuration, callback, error_callback):
		self.configuration = configuration
		self.callback = callback
		self.error_callback = error_callback
		self.table = []
		self.all_roots = []

	def dump(self):
		self.session = self.configuration.get_database_session()
		self.configuration.get_router_table_redis(self._got_redis, self.error_callback)

	def _got_redis(self, redis):
		self.redis = redis
		self.redis.keys('instance_ids_*', self._got_instance_ids)

	def _got_instance_ids(self, instance_ids):
		self.all_roots = instance_ids
		pipeline = self.redis.pipeline(True)
		for instance_set in instance_ids:
			pipeline.smembers(instance_set)
		pipeline.execute(self._got_set_members)

	def _got_set_members(self, members):
		self.all_roots.reverse()
		for instance_set in members:
			# Infer the hostname from the key name.
			hostname = self.all_roots.pop().replace("instance_ids_", "")
			# Fetch out the instances. NOTE: This is quite intensive.
			instances = self.session.query(
				paasmaker.model.ApplicationInstance
			).filter(
				paasmaker.model.ApplicationInstance.instance_id.in_(instance_set)
			).all()

			# Fetch out the application IDs. We then reduce this to one.
			# This is purely for sorting the table. TODO: This is really intensive.
			application_ids = map(lambda x: x.application_instance_type.application_version.application_id, instances)
			if len(application_ids) > 0:
				application_id = max(application_ids)
			else:
				application_id = 0

			entry = {
				'hostname': hostname,
				'instances': instances,
				'application_id': application_id
			}
			self.table.append(entry)

		# Sort the table.
		# Sort by the application id first, and then the reverse hostname.
		# We reverse the hostname to keep subdomains together. (Also, refer
		# http://stackoverflow.com/questions/931092/reverse-a-string-in-python)
		self.table.sort(key=lambda x: "%d_%s" % (x['application_id'], x['hostname'][::1]))

		self.callback(self.table)
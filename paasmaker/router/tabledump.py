import paasmaker

# From: http://stackoverflow.com/questions/5389507/iterating-over-every-two-elements-in-a-list
from itertools import izip
def pairwise(iterable):
	"s -> (s0,s1), (s2,s3), (s4, s5), ..."
	a = iter(iterable)
	return izip(a, a)

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
		self.redis.keys('instances_*', self._got_instance_ids)

	def _got_instance_ids(self, instance_ids):
		self.all_roots = instance_ids
		pipeline = self.redis.pipeline(True)
		for instance_set in instance_ids:
			hostname = instance_set.replace("instances_", "")
			# Fetch the instance IDs for this.
			pipeline.smembers("instance_ids_%s" % hostname)
			# Also fetch the instance routes.
			pipeline.smembers(instance_set)
		pipeline.execute(self._got_set_members)

	def _got_set_members(self, members):
		self.all_roots.reverse()
		for instance_set, instance_routes in pairwise(members):
			# Infer the hostname from the key name.
			hostname = self.all_roots.pop().replace("instances_", "")
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

			sorted_routes = list(instance_routes)
			sorted_routes.sort()
			entry = {
				'hostname': hostname,
				'instances': instances,
				'application_id': application_id,
				'routes': sorted_routes
			}
			self.table.append(entry)

		# Sort the table.
		# Sort by the application id first, and then the reverse hostname.
		# We reverse the hostname to keep subdomains together. (Also, refer
		# http://stackoverflow.com/questions/931092/reverse-a-string-in-python)
		self.table.sort(key=lambda x: "%d_%s" % (x['application_id'], x['hostname'][::1]))

		self.callback(self.table)
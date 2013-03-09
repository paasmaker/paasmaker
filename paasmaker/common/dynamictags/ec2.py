
import platform

import paasmaker
from base import BaseDynamicTags, BaseDynamicTagsTest

import tornado

class EC2DynamicTags(BaseDynamicTags):
	API_VERSION = "0.9.0"

	def fetch(self, existing_tags, callback):
		# Store a few possibly helpful tags for the node.
		self._tags = existing_tags
		self.callback = callback

		def got_availability_zone(availability_zone):
			self._tags['ec2']['availability-zone'] = availability_zone

			# That's all the tags we're fetching.
			self.callback(self._tags)

		def got_instance_type(instance_type):
			self._tags['ec2']['instance-type'] = instance_type

			self._fetch_tag('placement/availability-zone', got_availability_zone)

		def got_instance_id(instance_id):
			if not 'ec2' in self._tags:
				self._tags['ec2'] = {}

			self._tags['ec2']['instance-id'] = instance_id

			self._fetch_tag('instance-type', got_instance_type)

		self._fetch_tag('instance-id', got_instance_id)

	def _fetch_tag(self, tag, callback):
		def got_response(response):
			self._handle_fetch(response, callback)

		request = tornado.httpclient.HTTPRequest(
			"http://169.254.169.254/latest/meta-data/%s" % tag,
			method="GET",
			connect_timeout=1.0, # These are short - the host should respond very quickly.
			request_timeout=1.0) # These timeout speed it up if it's not used on EC2 instances.
		client = tornado.httpclient.AsyncHTTPClient(io_loop=self.configuration.io_loop)
		client.fetch(request, got_response)

	def _handle_fetch(self, response, callback):
		if response.error:
			# Didn't succeed. Probably not on EC2.
			self.logger.error("Unable to get metadata: %s", response.error)
			self.logger.error("Probably not running on EC2. Skipping.")

			# Don't call the supplied callback, just exit now.
			self.callback(self._tags)
		else:
			callback(response.body)

class EC2DynamicTagsTest(BaseDynamicTagsTest):
	def setUp(self):
		super(EC2DynamicTagsTest, self).setUp()

		self.configuration.plugins.register(
			'paasmaker.dynamictags.ec2',
			'paasmaker.common.dynamictags.ec2.EC2DynamicTags',
			{},
			'EC2 Dynamic Tags generator'
		)

	def test_simple(self):
		plugin = self.configuration.plugins.instantiate(
			'paasmaker.dynamictags.ec2',
			paasmaker.util.plugin.MODE.NODE_DYNAMIC_TAGS
		)

		tags = {}
		plugin.fetch(tags, self.stop)
		self.wait()

		# TODO: Find a way to test this when not on EC2.
		if 'ec2' in tags:
			self.assertTrue('instance-id' in tags['ec2'], "Missing instance ID")
			self.assertTrue('instance-type' in tags['ec2'], "Missing instance type")
			self.assertTrue('availability-zone' in tags['ec2'], "Availability zone missing")
		else:
			self.assertFalse('ec2' in tags, "Was not on EC2")

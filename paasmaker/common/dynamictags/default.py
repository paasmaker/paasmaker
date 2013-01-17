
import platform

import paasmaker
from base import BaseDynamicTags, BaseDynamicTagsTest

class DefaultDynamicTags(BaseDynamicTags):

	def fetch(self, existing_tags):
		# Store a few possibly helpful tags for the node.
		tags = {}
		tags['system'] = platform.system()
		tags['architecture'] = platform.architecture()[0]
		tags['machine'] = platform.system()
		tags['release'] = platform.release()

		existing_tags['platform'] = tags

class DefaultDynamicTagsTest(BaseDynamicTagsTest):
	def setUp(self):
		super(DefaultDynamicTagsTest, self).setUp()

		self.configuration.plugins.register(
			'paasmaker.dynamictags.default',
			'paasmaker.common.dynamictags.default.DefaultDynamicTags',
			{},
			'Default Dynamic Tags generator'
		)

	def test_simple(self):
		plugin = self.configuration.plugins.instantiate(
			'paasmaker.dynamictags.default',
			paasmaker.util.plugin.MODE.NODE_DYNAMIC_TAGS
		)

		tags = {}
		plugin.fetch(tags)

		self.assertTrue(tags.has_key('platform'), "Missing platform tags.")
		self.assertTrue(tags['platform'].has_key('system'), "Missing system tag.")

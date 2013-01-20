
import paasmaker

import tornado.testing
import colander

class BaseDynamicTagsConfigurationSchema(colander.MappingSchema):
	# No options defined.
	pass

class BaseDynamicTags(paasmaker.util.plugin.Plugin):
	MODES = {
		paasmaker.util.plugin.MODE.NODE_DYNAMIC_TAGS: None
	}
	OPTIONS_SCHEMA = BaseDynamicTagsConfigurationSchema()

	def fetch(self, existing_tags, callback):
		"""
		Alter or insert into the provided existing tags array. Call the callback
		once completed with the tags.

		For example::

			def fetch(self, existing_tags, callback):
				existing_tags['my_node_tag'] = "tag"
				callback(existing_tags)

		:arg dict existing_tags: The existing node tags.
		:arg callable callback: The callback to call once done.
		"""
		raise NotImplementedError("You must implement fetch().")

class BaseDynamicTagsTest(tornado.testing.AsyncTestCase):
	def setUp(self):
		super(BaseDynamicTagsTest, self).setUp()
		self.configuration = paasmaker.common.configuration.ConfigurationStub(0, ['pacemaker'], io_loop=self.io_loop)

	def tearDown(self):
		self.configuration.cleanup()
		super(BaseDynamicTagsTest, self).tearDown()
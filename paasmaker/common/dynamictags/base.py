
import paasmaker

import tornado.testing
import colander

class BaseDynamicTagsConfigurationSchema(colander.MappingSchema):
	# No options defined.
	pass

class BaseDynamicTags(paasmaker.util.plugin.Plugin):
	"""
	This plugin type is used to build a set of tags for the node
	programatically. For example, EC2 nodes might use this to submit
	additional tags about the region that the node is in, which applications
	or placement algorithms can use to better locate applications.

	You only need to implement the fetch() function in your subclass.

	Note that Paasmaker will only call your plugin once per server startup,
	and cache the results to be used for any future registration updates.

	For an example, have a look at the default dynamic tags plugin.
	"""
	MODES = {
		paasmaker.util.plugin.MODE.NODE_DYNAMIC_TAGS: None
	}
	OPTIONS_SCHEMA = BaseDynamicTagsConfigurationSchema()

	def fetch(self, existing_tags, callback):
		"""
		Alter or insert into the provided existing tags array. Call the callback
		once completed with the tags. The callback allows you to perform asynchronous
		actions to fetch your tags.

		Note that you alter the given existing_tags dict directly.

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
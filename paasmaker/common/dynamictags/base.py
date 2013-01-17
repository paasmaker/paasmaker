
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

	def fetch(self, existing_tags):
		"""
		Alter or insert into the provided existing tags array. Return nothing.
		This is called synchronously, so you won't want to spend too long doing
		things, although it is only called once upon node startup.
		"""
		raise NotImplementedError("You must implement fetch().")

class BaseDynamicTagsTest(tornado.testing.AsyncTestCase):
	def setUp(self):
		super(BaseDynamicTagsTest, self).setUp()
		self.configuration = paasmaker.common.configuration.ConfigurationStub(0, ['pacemaker'], io_loop=self.io_loop)

	def tearDown(self):
		self.configuration.cleanup()
		super(BaseDynamicTagsTest, self).tearDown()
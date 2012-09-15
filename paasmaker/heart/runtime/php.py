
from base import BaseRuntime, BaseRuntimeTest
import colander

class PHPRuntimeOptionsSchema(colander.MappingSchema):
	# TODO: Add more validation to these, eg, check that they exist and
	# are writable and stuff.
	apache_config_dir = colander.SchemaNode(colander.String(),
		title="Apache Configuration directory",
		description="The directory to drop instance configuration files into. Must exist and be writable.")
	apache_graceful_command = colander.SchemaNode(colander.String(),
		title="Apache Graceful command",
		description="The command to graceful apache to add or remove instances.",
		default="sudo apache2ctl graceful",
		missing="sudo apache2ctl graceful")

class PHPRuntimeParametersSchema(colander.MappingSchema):
	document_root = colander.SchemaNode(colander.String(),
		title="Document root",
		description="The subfolder under the application folder that is the document root.")
	apc = colander.SchemaNode(colander.Boolean(),
		title="Enable APC",
		desription="If APC should be enabled (default to True).",
		missing=True,
		default=True)
	openbasedir = colander.SchemaNode(colander.String(),
		title="Openbasedir restrictions",
		description="If openbasedir restrictions should be in place (default to False).",
		missing=False,
		default=False)

class PHPRuntime(BaseRuntime):
	def get_options_schema(self):
		return PHPRuntimeOptionsSchema()
	def get_parameters_schema(self):
		return PHPRuntimeParametersSchema()

	# TODO: Implement the rest of this...

class PHPRuntimeTest(BaseRuntimeTest):
	def setUp(self):
		super(PHPRuntimeTest, self).setUp()

		# Select a directory for apache.
		# TODO: Do this...

	def tearDown(self):
		super(PHPRuntimeTest, self).tearDown()

	def test_options(self):
		self.registry.register('paasmaker.runtime.php', 'paasmaker.heart.runtime.PHPRuntime', {'apache_config_dir': 'value'})
		instance = self.registry.instantiate('paasmaker.runtime.php', {'document_root': 'web/'})
		self.assertTrue(True, "Should have got here...")
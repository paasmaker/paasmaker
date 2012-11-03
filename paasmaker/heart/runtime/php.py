
import subprocess
import re

import paasmaker
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
	MODES = [paasmaker.util.plugin.MODE.RUNTIME_STARTUP, paasmaker.util.plugin.MODE.RUNTIME_VERSIONS]
	OPTIONS_SCHEMA = PHPRuntimeOptionsSchema()
	PARAMETERS_SCHEMA = PHPRuntimeParametersSchema()

	def get_versions(self):
		# TODO: Handle when this fails, rather than letting it bubble.
		raw_version = subprocess.check_output(['php', '-v'])
		# Parse out the version number.
		match = re.match(r'PHP ([\d.]+)', raw_version)
		if match:
			version = match.group(1)
			bits = version.split(".")
			major_version = ".".join(bits[0:2])

			return [major_version, version]
		else:
			# No versions available.
			return []

	# TODO: Implement the rest of this...

class PHPRuntimeTest(BaseRuntimeTest):

	def test_options(self):
		self.configuration.plugins.register('paasmaker.runtime.php', 'paasmaker.heart.runtime.PHPRuntime', {'apache_config_dir': 'value'})
		instance = self.configuration.plugins.instantiate('paasmaker.runtime.php', paasmaker.util.plugin.MODE.RUNTIME_STARTUP, {'document_root': 'web/'})
		self.assertTrue(True, "Should have got here...")

	def test_versions(self):
		self.configuration.plugins.register('paasmaker.runtime.php', 'paasmaker.heart.runtime.PHPRuntime', {'apache_config_dir': 'value'})
		instance = self.configuration.plugins.instantiate('paasmaker.runtime.php', paasmaker.util.plugin.MODE.RUNTIME_VERSIONS)

		versions = instance.get_versions()

		comparison = subprocess.check_output(['php', '-v'])
		self.assertEquals(len(versions), 2, "Should have returned two values.")
		self.assertEquals(versions[0], versions[1][0:len(versions[0])], "First version should have been substring of later version.")
		for version in versions:
			self.assertIn(".", version, "Version is not properly qualified.")
			self.assertIn(version, comparison, "Missing version in output.")
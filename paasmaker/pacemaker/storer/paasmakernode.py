
import os
import shutil

from base import BaseStorer, BaseStorerTest
import paasmaker

import colander

class PaasmakerNodeStorer(BaseStorer):
	API_VERSION = "0.9.0"

	def store(self, package_file, package_checksum, package_type, callback, error_callback):
		# Well, this one is easy.
		# The file remains here, so we just emit a URL that contains
		# the node UUID and the base filename.
		# TODO: To make this more useful, check if the package_file exists in the
		# packed directory. If not, move it into there - this will allow users to upload
		# pre-prepared versions of the code and have it go into the correct location.
		package_name = os.path.basename(package_file)
		source_path = "paasmaker://%s/%s" % (self.configuration.get_node_uuid(), package_name)

		callback(source_path, "Stored package successfully.")

class PaasmakerNodeStorerTest(BaseStorerTest):
	def test_simple(self):
		logger = self.configuration.get_job_logger('teststorer')
		self.configuration.set_node_uuid('thisnode')

		self.registry.register(
			'paasmaker.storer.paasmakernode',
			'paasmaker.pacemaker.storer.paasmakernode.PaasmakerNodeStorer',
			{},
			'Paasmaker Local file storer'
		)

		storer = self.registry.instantiate(
			'paasmaker.storer.paasmakernode',
			paasmaker.util.plugin.MODE.STORER,
			{},
			logger
		)

		# If we supply it with a filename, it should return
		# a paasmaker:// url.
		storer.store(
			"/tmp/test/package.tar.gz",
			"none",
			"tarball",
			self.success_callback,
			self.failure_callback
		)

		self.assertTrue(self.success, "Did not succeed.")
		self.assertTrue(self.url.startswith("paasmaker://"), "Incorrect scheme.")
		self.assertIn("/thisnode/", self.url, "Missing node UUID.")
		self.assertIn("/package.tar.gz", self.url, "Missing filename.")
		self.assertNotIn("/tmp/test/package.tar.gz", self.url, "Had entire path in URL.")
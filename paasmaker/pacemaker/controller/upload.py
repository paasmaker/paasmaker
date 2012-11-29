import unittest
import uuid
import logging
import json
import hashlib
import os
import glob
import tempfile
import subprocess

import paasmaker
from paasmaker.common.controller import BaseController, BaseControllerTest
from user import UserEditController

import tornado
import tornado.testing
import colander

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

class UploadChunkSchema(colander.MappingSchema):
	resumableChunkNumber = colander.SchemaNode(colander.Integer())
	resumableChunkSize = colander.SchemaNode(colander.Integer())
	resumableTotalSize = colander.SchemaNode(colander.Integer())
	resumableIdentifier = colander.SchemaNode(colander.String())
	resumableFilename = colander.SchemaNode(colander.String())
	resumableRelativePath = colander.SchemaNode(colander.String())

class UploadController(BaseController):
	AUTH_METHODS = [BaseController.USER]

	def _identifier(self):
		# Hash the identifier. (We don't take chances with user input)
		# Also, we add the user key to the mix, so that users don't overwrite
		# each others files.
		md5 = hashlib.md5()
		user = self.get_current_user()
		md5.update(user.apikey)
		md5.update(self.param('resumableIdentifier'))
		identifier = md5.hexdigest()

		return identifier

	def _chunk_path(self):
		temp_path = self.configuration.get_scratch_path_exists('partialuploads')
		temp_file = os.path.join(temp_path, "%s.%06d" % (self._identifier(), int(self.param('resumableChunkNumber'))))

		return temp_file

	def get(self):
		# Force JSON response.
		self._set_format('json')

		# Test to see if a chunk exists. Return 200 if it does,
		# or 404 otherwise.
		if os.path.exists(self._chunk_path()):
			self.add_data('success', True)
			self.add_data('identifier', self._identifier())
			self.render("api/apionly.html")
		else:
			self.add_error('No such chunk')
			self.add_data('success', False)
			self.add_data('identifier', self._identifier())
			self.write_error(404)

	def post(self):
		# TODO: Permissions.
		# TODO: Prevent users from filling up the disk?
		# LONG TERM TODO: This limits us to a single Pacemaker at the moment...

		# Force JSON response.
		self._set_format('json')

		self.validate_data(UploadChunkSchema())

		temp_file = self._chunk_path()

		if not self.request.files.has_key('file.data'):
			self.add_error('No file uploaded.')
			self.write_error(500)
		else:
			fileinfo = self.request.files['file.data'][0]
			fp = open(temp_file, 'w')
			fp.write(fileinfo['body'])
			fp.close()

			# See if we have all the parts.
			identifier = self._identifier()
			temp_path = self.configuration.get_scratch_path_exists('partialuploads')
			parts = glob.glob(os.path.join(temp_path, "%s.*" % identifier))
			parts.sort()
			if len(parts) * int(self.param('resumableChunkSize')) >= int(self.param('resumableTotalSize')):
				logger.info("Assembling file because we have all the parts.")
				# Must have all the parts.
				# TODO: Make async.
				output_path = self.configuration.get_scratch_path_exists('uploads')
				output_file = os.path.join(output_path, "%s" % identifier)
				fp = open(output_file, 'w')
				for part in parts:
					partfp = open(part, 'r')
					fp.write(partfp.read())
					partfp.close()
				fp.close()
				logger.info("Finished assembling file.")

			# Send back a 200 response code.
			self.add_data('success', True)
			self.add_data('identifier', identifier)
			self.render("api/apionly.html")

	@staticmethod
	def get_routes(configuration):
		routes = []
		routes.append((r"/files/upload", UploadController, configuration))
		return routes

class UploadControllerTest(BaseControllerTest):
	config_modules = ['pacemaker']

	def get_app(self):
		self.late_init_configuration(self.io_loop)
		routes = UploadController.get_routes({'configuration': self.configuration})
		routes.extend(UserEditController.get_routes({'configuration': self.configuration}))
		application = tornado.web.Application(routes, **self.configuration.get_tornado_configuration())
		return application

	def test_simple(self):
		# Create a user.
		request = paasmaker.common.api.user.UserCreateAPIRequest(self.configuration)
		request.set_user_params('User Name', 'username', 'username@example.com', True)
		request.set_user_password('testtest')
		request.send(self.stop)
		response = self.wait()

		self.failIf(not response.success)

		# Fetch that user from the db.
		session = self.configuration.get_database_session()
		user = session.query(paasmaker.model.User).get(response.data['user']['id'])
		apikey = user.apikey

		def progress_callback(position, total):
			logger.info("Progress: %d of %d bytes uploaded.", position, total)

		# Create a test file.
		uploadfile = tempfile.mkstemp()[1]
		# 1MiB - a good test because it doesn't align to a binary boundary.
		testdata = "Hello" * 200000
		open(uploadfile, 'w').write(testdata)
		# Calculate the MD5 of the supplied file.
		incoming_sum = subprocess.check_output(['md5sum', uploadfile]).split(' ')[0]

		# Now, attempt to upload a file.
		request = paasmaker.common.api.upload.UploadFileAPIRequest(self.configuration)
		request.set_apikey_auth(apikey)
		request.send_file(uploadfile, progress_callback, self.stop, self.stop)
		result = self.wait()

		# Check that it succeeded.
		self.assertTrue(result['data']['success'], "Should have succeeded.")

		# Check that the destination file exists.
		output_path = self.configuration.get_scratch_path_exists('uploads')
		output_file = os.path.join(output_path, "%s" % result['data']['identifier'])

		self.assertTrue(os.path.exists(output_file), "Output path does not exist.")

		# Check that it's the same file.
		uploaded_sum = subprocess.check_output(['md5sum', output_file]).split(' ')[0]
		self.assertEquals(incoming_sum, uploaded_sum, "Uploaded file is not the same.")
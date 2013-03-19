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
from paasmaker.common.core import constants

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
		md5.update(self.params['resumableIdentifier'])
		identifier = md5.hexdigest()

		return identifier

	def _chunk_path(self):
		temp_path = self.configuration.get_scratch_path_exists('partialuploads')
		identifier = self._identifier()
		temp_file = os.path.join(temp_path, "%s.%06d" % (identifier, int(self.params['resumableChunkNumber'])))

		return temp_file

	def get(self):
		# Force JSON response.
		self._set_format('json')

		self.require_permission(constants.PERMISSION.FILE_UPLOAD)

		valid_data = self.validate_data(UploadChunkSchema())

		# Test to see if a chunk exists. Return 200 if it does,
		# or 404 otherwise.
		identifier = self._identifier()
		chunk_path = self._chunk_path()
		if os.path.exists(chunk_path):
			self.add_data('success', True)
			self.add_data('identifier', identifier)
			self.render("api/apionly.html")
		else:
			self.add_error('No such chunk')
			self.add_data('success', False)
			self.add_data('identifier', identifier)
			self.write_error(404)

	def post(self):
		# Force JSON response.
		self._set_format('json')

		self.require_permission(constants.PERMISSION.FILE_UPLOAD)
		# TODO: Prevent users from filling up the disk?
		# LONG TERM TODO: This limits us to a single Pacemaker at the moment...

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
			# Rather than relying on the count of the chunks (because resumable.js will
			# upload more on the last chunk) just total the size of each part and use that.
			totalsize = 0
			for part in parts:
				totalsize += os.path.getsize(part)

			self.add_data('identifier', identifier)

			if totalsize == int(self.params['resumableTotalSize']):
				logger.info("Assembling file because we have all the parts.")
				# Must have all the parts.
				output_path = self.configuration.get_scratch_path_exists('uploads')
				output_file = os.path.join(output_path, "%s" % identifier)

				# Get ready to async assemble.
				fp = open(output_file, 'w')
				parts.reverse()

				def assemble_chunk():
					try:
						part = parts.pop()
						partfp = open(part, 'r')
						fp.write(partfp.read())
						partfp.close()
						os.unlink(part)

						# Call us back in the next IO loop iteration.
						self.configuration.io_loop.add_callback(assemble_chunk)
					except IndexError, ex:
						# No more parts.
						fp.close()
						logger.info("Finished assembling file.")
						self._completed_upload()
					# end of assemble_chunk()

				# Start async processing of chunks.
				assemble_chunk()
			else:
				self._completed_upload()

	def _completed_upload(self):
		# Send back a 200 response code.
		self.add_data('success', True)
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
		request.set_superkey_auth()
		request.set_user_params('User Name', 'username', 'username@example.com', True)
		request.set_user_password('testtest')
		request.send(self.stop)
		response = self.wait()

		self.failIf(not response.success)

		# Fetch that user from the db.
		self.configuration.get_database_session(self.stop, None)
		session = self.wait()
		user = session.query(paasmaker.model.User).get(response.data['user']['id'])
		apikey = user.apikey

		# And give them permission to upload a file.
		# TODO: Check permissions work as well.
		role = paasmaker.model.Role()
		role.name = "Upload"
		role.permissions = [constants.PERMISSION.FILE_UPLOAD]
		session.add(role)
		allocation = paasmaker.model.WorkspaceUserRole()
		allocation.user = user
		allocation.role = role
		session.add(allocation)
		paasmaker.model.WorkspaceUserRoleFlat.build_flat_table(session)

		def progress_callback(position, total):
			logger.info("Progress: %d of %d bytes uploaded.", position, total)

		# Create a test file.
		uploadfile = tempfile.mkstemp()[1]
		# 1MiB - a good test because it doesn't align to a binary boundary.
		# NOTE: This boundary doesn't match the server boundary. If it
		# does, a subtle bug can be allowed to exist.
		testdata = "Hello" * 400000
		open(uploadfile, 'w').write(testdata)
		# Calculate the MD5 of the supplied file.
		calc = paasmaker.util.streamingchecksum.StreamingChecksum(uploadfile, self.io_loop, logging)
		calc.start(self.stop)
		incoming_sum = self.wait()

		# Now, attempt to upload a file.
		request = paasmaker.common.api.upload.UploadFileAPIRequest(self.configuration)
		request.set_auth(apikey)
		request.send_file(uploadfile, progress_callback, self.stop, self.stop)
		result = self.wait()

		# Check that it succeeded.
		self.assertTrue(result['data']['success'], "Should have succeeded.")

		# Check that the destination file exists.
		output_path = self.configuration.get_scratch_path_exists('uploads')
		output_file = os.path.join(output_path, "%s" % result['data']['identifier'])

		self.assertTrue(os.path.exists(output_file), "Output path does not exist.")

		# Check that it's the same file.
		calc = paasmaker.util.streamingchecksum.StreamingChecksum(output_file, self.io_loop, logging)
		calc.start(self.stop)
		uploaded_sum = self.wait()

		self.assertEquals(incoming_sum, uploaded_sum, "Uploaded file is not the same.")


import os
import unittest

import paasmaker
from base import BaseService, BaseServiceTest

import colander
from boto.s3.connection import S3Connection

# TODO: Use the API to create an IAM sandboxed bucket, and supply that
# sandbox to the application, for enhanced security, rather than supplying
# it with the same credentials.
# TODO: Add an option to get an exact bucket name rather
# than having the uniqueness in it.

class S3BucketServiceConfigurationSchema(colander.MappingSchema):
	prefix = colander.SchemaNode(
		colander.String(),
		title="Bucket Name Prefix",
		description="Prefix added to all bucket names.",
		default="",
		missing=""
	)
	postfix = colander.SchemaNode(
		colander.String(),
		title="Bucket Name Postfix",
		description="Postfix added to all bucket names.",
		default="",
		missing=""
	)
	default_region = colander.SchemaNode(
		colander.String(),
		title="Default Bucket Create Region",
		description="The default location to create a bucket in, if the application doesn't specify.",
		default="",
		missing=""
	)
	access_key = colander.SchemaNode(
		colander.String(),
		title="Amazon AWS Access Key",
		description="Amazon AWS Access Key, used to create buckets. Currently, this will be passed on to applications."
	)
	secret_key = colander.SchemaNode(
		colander.String(),
		title="Amazon AWS Secret Key",
		description="Amazon AWS Secret Key, used to create buckets. Currently, this will be passed on to applications."
	)

class S3BucketServiceParametersSchema(colander.MappingSchema):
	region = colander.SchemaNode(
		colander.String(),
		title="Region to create the bucket in",
		description="The region to create the bucket in. If not supplied, it will use the server's configured default.",
		default="",
		missing=""
	)

class S3BucketService(BaseService):
	"""
	This service creates a bucket on Amazon S3, and supplies the application
	with all the credentials required to connect to that S3 bucket to write
	objects.

	You can specify a region to create the bucket in, by supplying the 'region'
	parameter in your application's manifest.

	The credentials output by this service looks as follows::

		{
			"protocol": "s3",
			"bucket": "<bucket name>",
			"access_key": "<access key to use>",
			"secret_key": "<secret key to use>"
		}

	.. WARNING::
		Currently, this plugin passes the access key and secret key along to the
		application. In future, this plugin will create an appropriate IAM sandbox
		for the new bucket (including new credentials) and pass this along. Until
		this is implemented, any applications using this service will have the same
		permissions as the access key supplied - which could mean deleting buckets
		or tampering with other buckets contents.

		Please keep this limitation in mind when using this service, and consider
		the security implications of this limitation.
	"""
	MODES = {
		paasmaker.util.plugin.MODE.SERVICE_CREATE: S3BucketServiceParametersSchema(),
		paasmaker.util.plugin.MODE.SERVICE_DELETE: None
	}
	OPTIONS_SCHEMA = S3BucketServiceConfigurationSchema()
	API_VERSION = "0.9.0"

	def create(self, name, callback, error_callback):
		# Generate a bucket name.
		bucket_name = self._safe_name(name)

		# Apply the sysadmins prefix/postfix.
		bucket_name = "%s%s%s" % (
			self.options['prefix'],
			bucket_name,
			self.options['postfix']
		)

		region = self.parameters['region']
		if len(region) == 0:
			region = self.options['default_region']

		self.logger.info("Chosen bucket name %s", bucket_name)

		def success_create(message):
			# Done! Let's emit the service credentials.
			self.logger.info("Successfully created bucket.")

			# From http://docs.aws.amazon.com/general/latest/gr/rande.html#s3_region
			# TODO: Test properly.
			if region == '':
				endpoint = "s3.amazonaws.com"
			elif region == 'EU':
				endpoint = "s3-eu-west-1.amazonaws.com"
			else:
				endpoint = "s3-%s.amazonaws.com" % region

			credentials = {
				"protocol": 's3',
				"bucket": bucket_name,
				"access_key": self.options['access_key'],
				"secret_key": self.options['secret_key'],
				"endpoint": endpoint
			}

			callback(credentials, message)

		self.logger.info("Sending bucket create request...")
		self.logger.info("Please be patient, this can take a while.")
		creator = S3BucketServiceAsyncCreate(
			self.configuration.io_loop,
			success_create,
			error_callback
		)
		creator.work(bucket_name, region, self.options, self.parameters)

	def update(self, name, existing_credentials, callback, error_callback):
		callback(existing_credentials)

	def remove(self, name, existing_credentials, callback, error_callback):
		# Remove the bucket.
		bucket_name = existing_credentials['bucket']

		self.logger.info("Sending delete request for bucket %s.", bucket_name)

		self.logger.info("Sending bucket delete request...")
		self.logger.info("Please be patient, this can take a while.")
		deletor = S3BucketServiceAsyncDelete(
			self.configuration.io_loop,
			callback,
			error_callback
		)
		deletor.work(bucket_name, self.options)

class S3BucketServiceAsyncCreate(paasmaker.util.threadcallback.ThreadCallback):

	def _work(self, name, region, options, parameters):
		# Create the S3 bucket.
		connection = S3Connection(
			options['access_key'],
			options['secret_key']
		)

		bucket = connection.create_bucket(
			name,
			location=region
		)

		# And that should be it...
		self._callback("Created bucket %s in region '%s'." % (name, region))

class S3BucketServiceAsyncDelete(paasmaker.util.threadcallback.ThreadCallback):

	def _work(self, name, options):
		# Delete the S3 Bucket.
		connection = S3Connection(
			options['access_key'],
			options['secret_key']
		)

		bucket = connection.get_bucket(name)
		connection.delete_bucket(bucket)

		self._callback("Deleted bucket %s" % name)

class S3BucketServiceTest(BaseServiceTest):

	@unittest.skip("Requires access credentials.")
	def test_simple(self):
		logger = self.configuration.get_job_logger("tests3service")

		# CAUTION: When testing, you will need to put in some credentials
		# below. Don't check this in for obvious reasons. If you
		# do check it in... well, I guess you'll be changing your credentials.
		self.registry.register(
			'paasmaker.service.s3bucket',
			'paasmaker.pacemaker.service.s3bucket.S3BucketService',
			{
				'prefix': 'paasmaker',
				'postfix': 'test',
				'access_key': 'XXXXXXXXXXXXXXXXXXXXX',
				'secret_key': 'XXXXXXXXXXXXXXXXXXXXX',
				'default_region': 'ap-southeast-2'
			},
			'S3 Bucket Service'
		)
		service = self.registry.instantiate(
			'paasmaker.service.s3bucket',
			paasmaker.util.plugin.MODE.SERVICE_CREATE,
			{
			},
			logger=logger
		)

		service.create('test', self.success_callback, self.failure_callback)
		self.wait()

		self.assertTrue(self.success, "S3Service creation was not successful.")
		self.assertEquals(len(self.credentials), 5, "S3Service did not return expected number of keys.")
		self.assertTrue('bucket' in self.credentials, "S3Service did not return the bucket it created.")

		service.remove('test', self.credentials, self.success_remove_callback, self.failure_callback)
		# Wait for a bit longer than usual - this takes a while to go through.
		self.wait(timeout=15)

		self.assertTrue(self.success, "S3Service deletion was not successful.")


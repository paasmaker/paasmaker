Amazon S3 Bucket Service
========================

This service will automatically create a bucket on Amazon S3, and supply
to the application enough configuration to work with that bucket.

.. WARNING::
	This version of the plugin just hands the S3 credentials off to the
	application as-is. This is not secure if you do not trust your
	application. A future version of this plugin will be able to
	create a seperate IAM role just for that bucket and supply that to
	the application.

The application will get credentials that look like this:

.. code-block:: json

	{
		"protocol": "s3",
		"bucket": "<bucket name>",
		"access_key": "<access key to use>",
		"secret_key": "<secret key to use>",
		"endpoint": "<endpoint URL>"
	}

Regions are the symbolic region names from `Amazon's documentation
on regions and endpoints <http://docs.aws.amazon.com/general/latest/gr/rande.html>`_.
Note that some regions have unusual names, so be sure to check that list.

To enable the plugin:

.. code-block:: yaml

	plugins:
	- class: paasmaker.pacemaker.service.s3bucket.S3BucketService
	  name: paasmaker.service.s3bucket
	  title: Amazon S3 Bucket Service
	  parameters:
	    access_key: <access key>
	    secret_key: <secret key>

Application Configuration
-------------------------

.. colanderdoc:: paasmaker.pacemaker.service.s3bucket.S3BucketServiceParametersSchema

	The plugin has the following configuration options:

Server Configuration
--------------------

.. colanderdoc:: paasmaker.pacemaker.service.s3bucket.S3BucketServiceConfigurationSchema

	The plugin has the following configuration options:
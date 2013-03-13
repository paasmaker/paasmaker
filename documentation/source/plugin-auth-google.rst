Google OpenID authentication Plugin
===================================

This plugin allows you to handle OpenID logins, using a Google
account to authenticate against. This could be useful for organisations
that are using Google Apps internally.

Once it has been added, on the login page, you will see a list of other
login providers underneath the username and password area. It will appear
in the list with the title of the plugin as registered in the configuration
file.

The first time a user logs in, a record is created in the Paasmaker database
to match up that user. That user is not granted any permissions. Another
user who can grant permissions will need to assign a role to that user.

To enable the plugin:

.. code-block:: yaml

	plugins:
	- class: paasmaker.pacemaker.auth.google.GoogleAuthMetadata
	  name: paasmaker.auth.google
	  title: Google OpenID authentication

Server Configuration
--------------------

This plugin currently has no options. In future, it is planned to update
it to limit logins to only certain email domain names (for example, to
limit it to your organisation) and to automatically assign roles.
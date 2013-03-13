Allow Any authentication Plugin
===============================

This plugin, primarily intended for testing purposes only, automatically
creates an account when someone tries to log in. It does not reset passwords
on existing accounts.

The first time a user logs in, a record is created in the Paasmaker database
to match up that user. That user is not granted any permissions. Another
user who can grant permissions will need to assign a role to that user.

To enable the plugin:

.. code-block:: yaml

	plugins:
	- class: paasmaker.pacemaker.auth.allowany.AllowAnyAuth
	  name: paasmaker.auth.allowany
	  title: Allow Any Authentication

Server Configuration
--------------------

This plugin has no configuration options.
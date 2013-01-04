
API Data format and Authentication
==================================

Every single URI in Paasmaker is designed to be used by as an API endpoint.
Where possible, each URI also tries to act as a HTML front end for users as well.

To access any page in JSON format, append ``?format=json`` to the URL, to fetch
the JSON version of it. For URIs that support POST, you can also send along a JSON
encoded body that the server will parse and then use as input for that request.

JSON POST format
----------------

When you POST data in JSON format, the structure of the body should be as so::

    {
        "auth": {
            "method": "method",
            "value": "value"
        },
        "data": {
            "key1": "here",
            ...
        }
    }

The valid values for auth are described in the section below. The data section
can contain any keys, nested as appropriate, for the controller action.

Authentication
--------------

There are many ways to authenticate with the system. Many options have been
presented to best fit in with how you want to interact with the system.

Authentication falls into four categories:

* **User**: Where a user is logged into the system.
* **Super Token**: Pacemakers can be configured to accept a 'super token'.
  When presented with the token, all permissions are granted. This is
  primarily designed to bootstrap the system and create the initial users.
* **Node Token**: this is designed to allow nodes to communicate with each
  other with a seperate secret token. Each node in a cluster should be
  configured with the same token to allow them to authenticate and talk
  to each other.
* **Anonymous**: some controllers permit anonymous access. In this case,
  no authentication is required or checked.

When making HTTP requests, you can pass along these HTTP headers to
authenticate:

* ``Node-Token`` - if this header's value is a valid node token that matches
  the configuration's token, access is granted. However, it's only available
  to controllers that allow Node authentication.
* ``Super-Token`` - if this header's value matches the pacemaker's super token,
  access is granted. The matching controller needs to allow super token access.
* A standard cookie header, with an appropriate secure value that matches the
  logged in user. The values expire after a time specified in the configuration;
  so this is not recommended for long term use.
* ``User-Token`` - if this header contains the same value as an API key for a
  user in the database, that user is granted access to the system with the
  permissions defined for the user.

If you send a JSON POST body, the following method strings can be used:

* ``token`` - if the value matches a user's API key, that user is considered
  to be logged in.
* ``super`` - if the value matches the nodes configured super token, and
  super tokens are enabled, then the request will be allowed.
* ``node`` - if the value matches the configured node token, access is allowed
  where the controller permits it.
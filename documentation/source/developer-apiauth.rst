
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
        "auth": "value",
        "data": {
            "key1": "here",
            ...
        }
    }

The valid values for auth are described in the section below. The data section
can contain any keys, nested as appropriate, for the controller action. Auth
can also be omitted, if you authenticate using a HTTP header.

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

When making HTTP requests, you can include a `Auth-Paasmaker` header, that
contains either a super token, a node token, or a user's API key. The
controller will automatically detect the type of token and grant access
if it matches.

If you send a JSON POST body, you can include the "auth" key in the root,
which is just a string. This follows the same rules as for the HTTP header.
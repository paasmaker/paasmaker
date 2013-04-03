Controllers
===========

The HTTP controllers form the API and web console endpoints
for Paasmaker. The command line tool uses the API to communicate,
so the HTTP controllers are the input and the output for the whole
system.

The :class:`BaseController` class is the parent class for
all the controllers, and tries to offload some repetitive tasks
that other controllers would need to perform.

``BaseController`` itself is a subclass of Tornado's Request
handler, but takes argument processing and security in a different
direction.

Different node types
--------------------

Only Pacemaker nodes have access to an SQL database, but all types
of nodes have HTTP endpoints. On non-pacemaker nodes, you can only
authenticate with the ANONYMOUS or NODE methods. Additionally, you
can not get a database session, and the controller will raise
an exception if you try. Otherwise, the controllers function
identically.

Asynchronous requests
---------------------

In normal Tornado, you need to explicitly put requests into
asynchronous mode by adding a decorator to the method:

.. code-block:: python

	class MyController(BaseController):
		@tornado.web.asynchronous
		def get(self):
			.. do stuff ..

However, all Paasmaker controller actions are automatically
asynchronous. This means that you must call ``render()`` to
end the request (either in ``get()/post()`` or a callback),
otherwise the request will never return to the client. Normally
in Tornado, without the ``@asynchronous`` decorator, the request
would end at the end of the ``get()/post()`` functions.

So, for example, in Paasmaker:

.. code-block:: python

	class MyController(BaseController):
		def get(self):
			# Doesn't need the @tornado.web.asynchronous decorator.
			.. do stuff ..
			self.configuration.io_loop.add_callback(self.done_now)

		def done_now(self):
			self.render("api/apionly.html")

Request Mode
------------

Requests are considered to be in one of two modes. They
are ``html`` or ``json``. This is controlled by adding ``?format=json``
to the end of the URI.

In the future, we may offer additional output formats.

In HTML mode, it is expected that you are returned a HTML page. In
JSON mode, you are instead returned body with content type ``application/json``
and a JSON encoded representation of the results of that controller.

See the section on rendering for how variables are selected for output.

Argument processing
-------------------

In the ``prepare()`` method, the first thing it does is handle
it's input arguments. Tornado provides the ``get_argument()``
helper function, that returns a named GET or POST variable.

Paasmaker takes this a few steps further. Firstly, in case of POST
request, it does a check to see if the body of the request is JSON
(it detects looking for ``{`` and ``}`` at each end). If so,
it :doc:`decodes the JSON according to the format <developer-apiauth>`
and feeds in those values as arguments. The parsed JSON is parsed in
as a nested dictionary, preserving the original structure.

As you are aware, HTTP POST requests from browsers return key/value pairs.
Paasmaker includes a class, called :class:`Flattenizr`, which takes
key/value pairs and converts that into a dictionary of possibly
nested values. This is then merged in with the arguments.

The raw results of this argument processing are placed in the instance
variable ``self.raw_params``. Unless you need to, don't access data
directly from this instance variable. It's not made private because there
are sometimes reasons to read directly from it (see below).

Argument validation
-------------------

The BaseController provides a helper method, ``validate_data()``,
that takes an instance of a Colander schema, and makes sure that the
parsed parameters match that schema. If they do not, and the request is
in JSON mode, it aborts the request with a ``400 Bad Request`` HTTP error
code, and a response body that should contain enought information to
determine what was invalid.

If the request is in HTML mode, the request does not abort, and the
``validate_data()`` function returns a boolean indicating the result.
It also sets the ``input_errors`` variable, as a dict, that indicates
what fields on the Colander schema failed. Finally, it copies in the raw
parameters into the parsed parameters.

The idea between the different validation handling of JSON and HTML
requests is for HTML forms. In the case of JSON requests, your request
has failed and should be retried. In the case of HTML mode, you may
want to refill the form with the data that the user supplied and re-render
it so they can have another go.

Assuming the data passes validation, it appears in the instance variable
``self.parameters``. Note that only the fields mentioned in the Colander schema
appear in ``parameters``. If you have a field that you can't validate via
Colander easily, you can fetch it out of ``raw_parameters`` directly.

As an example of validation, see the :class:`WorkspaceEditController`.

Authentication
--------------

Each controller class has a class variable called ``AUTH_METHODS``. This is a
list of constants from the ``BaseController``, and dictates what methods
are valid for authentication to this controller. The possible types are listed
below with a description of what they are:

* BaseController.ANONYMOUS - anyone can access this page without authenticating.
* BaseController.USER - a valid logged in user must be present. Note that individual
  permissions are checked later - this only ensures that they have a login. They can
  supply either an API key, or a valid login cookie to pass this requirement.
* BaseController.NODE - a valid node token must be presented. This is designed
  for nodes to talk to each other - for example, for registration.
* BaseController.SUPER - a valid super token is supplied. This user is not
  checked for permissions later.

Once the check is complete, the following instance variables are set. Do not
rely on these, as they will be changed and protected in the future.

* ``self.super_auth`` will be either True or False.
* ``self.get_current_user()`` will return a :class:``paasmaker.model.User``
  instance, or None if no user is logged in. This returns the correct value
  even if the user presented an API key.

To protect node only controllers, it is currently assumed that they only
permit node authentication. It is seen to be unlikely that node controllers
should be accessed by users.

Permissions
-----------

You can protect an entire action by requesting a specific permission be
present for the logged in user (and note that if you've authenticated with
a super token, this always succeeds):

.. code-block:: python

	self.require_permission(constants.PERMISSION.WORKSPACE_EDIT, workspace=workspace)

The first argument is the permission name, and the second optional argument
is the workspace to constrain the search to - you can omit it for a global
permission check. You should find the parent workspace of any other item
that you work on to supply to this function.

``require_permission()`` ends the request immediately with a ``403 Forbidden``.
If you just want to test the permissions (so as to do something else depending
on their permission level), use ``has_permission()``, which is the same except
it returns a boolean value instead:

.. code-block:: python

	cando = self.has_permission(constants.PERMISSION.WORKSPACE_EDIT, workspace=workspace)

Permissions are cached on request startup, so there is no cost for any permissions
check during your controller. Check as many permissions as you need.

The permissions system is covered in the :doc:`administrators permissions
manual <administrator-permissions>`.

Database
--------

Pacemaker nodes can access the database to generate the relevant content of pages.
Due to the fact that the database access library is SQLalchemy, it is synchronous,
so you should keep your queries as short as possible and only query on indexed
fields. Also, due to another quirk that makes the code simpler, any Pacemaker
controller request fetches a database session and hangs on to it until the end
of the request.

You can use the instance variable ``self.session`` to access the database. In future,
we hope to fix this so you fetch sessions on demand via a callback.

What we currently have works and will scale to moderate levels, but will be revisted
in the future.

Submitting Jobs
---------------

Sometimes, controllers don't actually return results at the time, and instead submit
a batch of jobs to accomplish a task. For example, starting an application launches
a tree of jobs.

The ``BaseController`` class has a helper method to render an appropriate page, or
return the Job ID depending on the mode that the request is in.

For example, here is a snippet from :class:`ApplicationNewController`:

.. code-block:: python

	def job_started():
		self._redirect_job(self.get_data('job_id'), '/workspace/%d/applications' % workspace.id)

	def application_job_ready(job_id):
		self.add_data('job_id', job_id)
		self.configuration.job_manager.allow_execution(job_id, callback=job_started)

	paasmaker.common.job.prepare.prepareroot.ApplicationPrepareRootJob.setup(
		self.configuration,
		application_name,
		self.params['manifest_path'],
		workspace.id,
		self.params['scm'],
		raw_scm_parameters,
		application_job_ready,
		application_id=application_id
	)

In JSON mode, this returns the following:

.. code-block:: json

	{
		'data': {
			'job_id': '<job UUID>'
		}
	}

But in HTML mode, returns a page that tracks the status of the job tree.

Rendering
---------

Paasmaker provides the following methods for supplying output variables:

* ``add_data(name, value)`` - adds a single named value for both JSON and
  HTML requests.
* ``add_data_template(name, value)`` - adds a value for the templates only.

When rendering, only values set with ``add_data`` are returned in the JSON
result. When rendering HTML templates, the values added with ``add_data`` and
``add_data_template`` are merged together. The reason this is done is because
the templates may require additional variables to perform it's duties, which
should not be exposed via the JSON API (for example, private credentials, unless
you have the right permissions).

To end the request and send it back to the client, generally you will use
the render method, which takes a single argument being the HTML template name.
This handles both HTML and JSON modes.

.. code-block:: python

	self.render("path/to/template.html")

If your request is JSON only, use ``api/apionly.html`` as the template.

JSON encoding
-------------

Basically, all the values added with ``add_data`` are put into a dictionary,
and that dictionary is json encoded with the built in Python JSON library.
However, some values are not serializable with that library, and a helper class,
:class:`paasmaker.util.jsonencoder.JsonEncoder` handles a few more types
than the built in encoder. The documentation for that describes what additional
types it handles and their representation.

However, a special note is ORM objects. ORM objects often contain private fields
that should not be shown to users, depending on their permission levels. Templates
can and should check permissions before adding these sensitive values into the
HTML output. To handle this for JSON requests, ORM objects have a ``flatten()``
method, that returns a dict of values ready for the encoder. Sometimes you want
to return additional fields other than the default (safe) set if the user has
permissions. You can add additional fields as in this example, which applies
for all objects of that type in this example, which is a snippet from :class:`ApplicationServiceListController`:

.. code-block:: python

	if self.has_permission(constants.PERMISSION.SERVICE_CREDENTIAL_VIEW, workspace=application.workspace):
		self.add_extra_data_fields(paasmaker.model.Service, 'credentials')

``credentials`` in this case is not automatically exposed as it may contain
sensitive information.

BaseController
--------------

.. autoclass:: paasmaker.common.controller.base.BaseController
    :members:
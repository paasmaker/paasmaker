
API Classes
=================

These classes provide ready to go Python API adaptors for Paasmaker.

They are designed to be used with a tornado IO loop, and will not work
otherwise.

Each of the API classes descend from a base class, which handles
authentication and pointing the requests at the correct server.

Workspace
---------

.. autoclass:: paasmaker.common.api.workspace.WorkspaceGetAPIRequest
    :members:

.. autoclass:: paasmaker.common.api.workspace.WorkspaceCreateAPIRequest
    :members:

.. autoclass:: paasmaker.common.api.workspace.WorkspaceEditAPIRequest
    :members:

.. autoclass:: paasmaker.common.api.workspace.WorkspaceListAPIRequest
    :members:

Application
-----------

.. autoclass:: paasmaker.common.api.application.ApplicationGetAPIRequest
    :members:

.. autoclass:: paasmaker.common.api.application.ApplicationListAPIRequest
    :members:

.. autoclass:: paasmaker.common.api.application.ApplicationNewAPIRequest
    :members:

.. autoclass:: paasmaker.common.api.application.ApplicationNewVersionAPIRequest
    :members:

.. autoclass:: paasmaker.common.api.application.ApplicationDeleteAPIRequest
    :members:

.. autoclass:: paasmaker.common.api.upload.UploadFileAPIRequest
    :members:

Version
-------

.. autoclass:: paasmaker.common.api.version.VersionGetAPIRequest
    :members:

.. autoclass:: paasmaker.common.api.version.VersionInstancesAPIRequest
    :members:

.. autoclass:: paasmaker.common.api.version.VersionActionRootAPIRequest
    :members:

.. autoclass:: paasmaker.common.api.version.VersionRegisterAPIRequest
    :members:

.. autoclass:: paasmaker.common.api.version.VersionStartAPIRequest
    :members:

.. autoclass:: paasmaker.common.api.version.VersionStopAPIRequest
    :members:

.. autoclass:: paasmaker.common.api.version.VersionDeRegisterAPIRequest
    :members:

.. autoclass:: paasmaker.common.api.version.VersionSetCurrentAPIRequest
    :members:

.. autoclass:: paasmaker.common.api.version.VersionDeleteAPIRequest
    :members:

Cluster
-------

.. autoclass:: paasmaker.common.api.nodelist.NodeListAPIRequest
    :members:

Users
-----

.. autoclass:: paasmaker.common.api.user.UserGetAPIRequest
    :members:

.. autoclass:: paasmaker.common.api.user.UserCreateAPIRequest
    :members:

.. autoclass:: paasmaker.common.api.user.UserEditAPIRequest
    :members:

.. autoclass:: paasmaker.common.api.user.UserListAPIRequest
    :members:

Roles and Role Allocations
--------------------------

.. autoclass:: paasmaker.common.api.role.RoleGetAPIRequest
    :members:

.. autoclass:: paasmaker.common.api.role.RoleCreateAPIRequest
    :members:

.. autoclass:: paasmaker.common.api.role.RoleEditAPIRequest
    :members:

.. autoclass:: paasmaker.common.api.role.RoleListAPIRequest
    :members:

.. autoclass:: paasmaker.common.api.role.RoleAllocationListAPIRequest
    :members:

.. autoclass:: paasmaker.common.api.role.RoleAllocationAPIRequest
    :members:

.. autoclass:: paasmaker.common.api.role.RoleUnAllocationAPIRequest
    :members:

Misc
----

.. autoclass:: paasmaker.common.api.login.LoginAPIRequest
    :members:

.. autoclass:: paasmaker.common.api.job.JobAbortAPIRequest
    :members:

.. autoclass:: paasmaker.common.api.information.InformationAPIRequest
    :members:

Streaming Updates
-----------------

.. autoclass:: paasmaker.common.api.log.LogStreamAPIRequest
    :members:

.. autoclass:: paasmaker.common.api.job.JobStreamAPIRequest
    :members:

.. autoclass:: paasmaker.common.api.router.RouterStreamAPIRequest
    :members:


Base Classes
--------------------

.. autoclass:: paasmaker.common.api.APIRequest
    :members:

.. autoclass:: paasmaker.common.api.APIResponse
    :members:

.. autoclass:: paasmaker.common.api.StreamAPIRequest
    :members:

Internal APIs
-------------

These internal APIs are used by nodes to talk to each other. You should not be using them,
and in fact will not be able to except with Node authentication. They are documented here
for completeness.

.. autoclass:: paasmaker.common.api.noderegister.NodeRegisterAPIRequest
    :members:

.. autoclass:: paasmaker.common.api.noderegister.NodeUpdateAPIRequest
    :members:

.. autoclass:: paasmaker.common.api.noderegister.NodeShutdownAPIRequest
    :members:

.. autoclass:: paasmaker.common.api.package.PackageSizeAPIRequest
    :members:

.. autoclass:: paasmaker.common.api.package.PackageDownloadAPIRequest
    :members:
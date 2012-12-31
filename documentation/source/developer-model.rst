
Database Models
=================

The database components are handled via the SQLAlchemy library.

The documentation below shows the model classes built in to Paasmaker,
and covers any special methods that they provide.

Base Class
----------

.. autoclass:: paasmaker.model.OrmBase
    :members:

Models
------

.. autoclass:: paasmaker.model.Node
    :members:

.. autoclass:: paasmaker.model.User
    :members:

.. autoclass:: paasmaker.model.Role
    :members:

.. autoclass:: paasmaker.model.RolePermission
    :members:

.. autoclass:: paasmaker.model.Workspace
    :members:

.. autoclass:: paasmaker.model.WorkspaceUserRole
    :members:

.. autoclass:: paasmaker.model.WorkspaceUserRoleFlat
    :members:

.. autoclass:: paasmaker.model.Application
    :members:

.. autoclass:: paasmaker.model.ApplicationVersion
    :members:

.. autoclass:: paasmaker.model.ApplicationInstanceType
    :members:

.. autoclass:: paasmaker.model.ApplicationInstance
    :members:

.. autoclass:: paasmaker.model.ApplicationInstanceTypeHostname
    :members:

.. autoclass:: paasmaker.model.ApplicationInstanceTypeCron
    :members:

.. autoclass:: paasmaker.model.Service
    :members:

Helpers
-------

.. autoclass:: paasmaker.model.WorkspaceUserRoleFlatCache
    :members:
Pacemaker plugins
=================

USER_AUTHENTICATE_PLAIN
-----------------------

.. autoclass:: paasmaker.pacemaker.auth.base.BaseAuth
    :members:

PLACEMENT
---------

.. autoclass:: paasmaker.pacemaker.placement.base.BasePlacement
    :members:

PREPARE_COMMAND and RUNTIME_STARTUP
-----------------------------------

These two plugin types are functionally identical, but are split
into two different modes in case the location needs to be restricted.

PREPARE_COMMAND is for Pacemakers only, and RUNTIME_STARTUP is for
hearts only. Both types decend from the same base class.

.. autoclass:: paasmaker.pacemaker.prepare.base.BasePrepare
    :members:

SCM_EXPORT and SCM_FORM
-----------------------

Currently, it is assumed that SCM_EXPORT plugins also implement the
SCM_FORM mode. This should probably be cleaned up at some stage.

.. autoclass:: paasmaker.pacemaker.scm.base.BaseSCM
    :members:

SCM_LIST
--------

.. autoclass:: paasmaker.pacemaker.scmlist.base.BaseSCMList
    :members:

PACKER
------

.. autoclass:: paasmaker.pacemaker.packer.base.BasePacker
    :members:

STORER
------

.. autoclass:: paasmaker.pacemaker.storer.base.BaseStorer
    :members:
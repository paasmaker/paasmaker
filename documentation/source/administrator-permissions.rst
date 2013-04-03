Permissions
===========

Paasmaker implements a very simple permissions system, based on roles
assigned to users, that affect either a single workspace, or a global
level.

Overview
--------

There are four types of objects that form the permissions system:

**Users**: Paasmaker has users who are able to log into the system.

**Workspaces**: Paasmaker uses :term:`workspaces <workspace>` as a
container for applications.

**Role**: A role is a named set of permissions.

**Role Allocation**: A role allocation ties together a user and a role,
and optionally specifies a workspace as well.

Managing Permissions
--------------------

The simplest way to describe Paasmaker's permissions system is with
a few examples.

Let's say that we have a user called "Daniel". That user has a record
in the database, which describes their password and other information
about that user.

This user should be allowed to do anything inside Paasmaker. For this,
a role was created called "Administrator". This role is configured to
have all permissions.

Then, to link that user and the role, a new role allocation is created.
The user is selected, as well as the role, and in this case, the workspace
is set to "Global". That means that any permissions granted by that role
apply to any workspace.

A role can be assigned to as many users as needed. Currently, Paasmaker
has no way to group users and assign a role to that group. It is hoped to
implement this in a future release.

For a second example, let's say we have a user called "developer". This
user should have the ability to do anything on the "Staging" workspace.
To accomplish this, a new role is created with all permissions. Then,
a new role allocation is created, matching the user with the role and
the Staging workspace.

At this stage, the "developer" role will have several permissions which
should grant that user the ability to manage users and roles. However,
when Paasmaker checks those permissions, it looks for a blank (unset)
workspace. As that role has been assigned to a specific workspace, those
tests fail and that user won't be able to manage users or roles. This
is a quirk of the current permissions system and should not be relied
upon to secure your installation.

Permissions
-----------

The available permissions and what they are for are below.

FILE_UPLOAD
	With this permission, a user is allowed to upload a file
	to a Pacemaker node, to be used to deploy an application.

JOB_ABORT
	With this permission, a user can abort a currently running
	job. At this time, no checks are made to ensure that the job
	belongs to any workspace; as Job IDs are hard to guess, we are
	currently relying on this to supply security. In the future,
	we hope to lock this down properly.

HEALTH_CHECK
	With this permission, the user can see the list of health
	check jobs, to monitor their status.

USER_LIST
	With this permission, the user can view the list of users.

USER_EDIT
	With this permission, the user can create and edit Paasmaker
	users.

ROLE_LIST
	With this permission, the user can view a list of roles.

ROLE_EDIT
	With this permission, the user can create and edit Paasmaker
	roles.

ROLE_ASSIGN
	With this permission, the user can assign roles to users and workspaces.

SYSTEM_ADMINISTRATION
	With this permission, the user can access several pages that
	describe the configuration of Paasmaker. This permission may
	grant the user access to pages that contain information like
	passwords from the server's configuration file.

SYSTEM_OVERVIEW
	With this permission, the user can view the overview page, which gives
	a summary of all workspaces on the system.

APPLICATION_ROUTING
	With this permission, the user can make adjustments to the routing
	table, such as making a specific version of an application current.
	Without this permission, they will not be able to select the current
	version.

NODE_LIST
	With this permission, the user can see a list of nodes that are part
	of the cluster.

NODE_DETAIL_VIEW
	With this permission, the user can view the detail page for a specific
	node. This page might reveal more information about a node than you
	may wish to grant.

WORKSPACE_LIST
	With this permission, the user can view a complete list of workspaces.

WORKSPACE_VIEW
	With this permission, the user can view workspaces. If you bind a role
	with this permission to a specific workspace, they will be able to view
	that workspace (and it will appear in a list of workspaces), but will be
	unable to make changes to it.

WORKSPACE_EDIT
	With this permission, the user can create or edit workspaces. If a role
	with this permission is bound to a specific workspace, then that workspace
	can be edited, but the user can not create new workspaces.

APPLICATION_CREATE
	With this permission, the user can create new applications, or deploy
	new versions of existing applications.

APPLICATION_DELETE
	With this permission, the user can delete an application.

APPLICATION_DEPLOY
	With this permission, the user can start, stop, register, and deregister
	instances.

APPLICATION_SERVICE_DETAIL
	With this permission, the user can view the full details for services
	on applications. This will allow them to see the full credentials for
	services, which may not be desirable.

APPLICATION_VIEW_MANIFEST
	Allows a user to view :doc:`manifest files <user-application-manifest>`
	uploaded with each version of any application in the workspace.
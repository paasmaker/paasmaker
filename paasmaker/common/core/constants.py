#
# Paasmaker - Platform as a Service
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#

# From http://stackoverflow.com/questions/36932/whats-the-best-way-to-implement-an-enum-in-python
# (Plus some tweaks)
# Why do this at all? Originally they were just strings and arrays of strings, and I used them
# in the code. I've several times implemented bugs where I put the wrong
# strings in, and the code waits for a state that doesn't exist. So yes, this adds
# code overhead, but in terms of a more reliable system long term, this should
# cut down on code errors, as it will fail when you try to reference them.
class Enum(set):
	"""
	A simple Enum class, to confirm that any requested attributes
	actually are part of the Enum, and also return the entire set if
	asked.

	This is based on `a stack overflow question <http://stackoverflow.com/questions/36932/whats-the-best-way-to-implement-an-enum-in-python>`_,
	with a modification to make it able to return all values.
	"""
	def __getattr__(self, name):
		if name == 'ALL':
			return list(self)
		if name in self:
			return name
		raise AttributeError

	def __setattr__(self, name, value):
		raise NotImplementedError("You should not try to set an Enum value.")
	def __delattr__(self, name, value):
		raise NotImplementedError("You should not try to delete an Enum value.")

# Possible Node States.
NODE = Enum(['ACTIVE', 'STOPPED', 'DOWN', 'INACTIVE'])

# Various classes of node states.
NODE_ACTIVE_STATES = [NODE.ACTIVE]
NODE_ERROR_STATES = [NODE.DOWN]
NODE_STOPPED_STATES = [NODE.STOPPED, NODE.DOWN]

# The possible job states.
JOB = Enum(['NEW', 'WAITING', 'RUNNING', 'FAILED', 'ABORTED', 'SUCCESS'])

# Various classes of job states.
JOB_RUNNING_STATES = [JOB.NEW, JOB.WAITING, JOB.RUNNING]
JOB_SUCCESS_STATES = [JOB.SUCCESS]
JOB_ERROR_STATES = [JOB.FAILED, JOB.ABORTED]
JOB_FINISHED_STATES = [JOB.ABORTED, JOB.SUCCESS, JOB.FAILED]

# The possible instance states.
INSTANCE = Enum(['ALLOCATED', 'REGISTERED', 'STARTING', 'RUNNING', 'SUSPENDED', 'STOPPED', 'ERROR', 'DOWN', 'DEREGISTERED'])

# Various classes of instance states.
INSTANCE_ALLOCATED_STATES = [INSTANCE.ALLOCATED, INSTANCE.REGISTERED, INSTANCE.STARTING, INSTANCE.RUNNING, INSTANCE.STOPPED, INSTANCE.SUSPENDED]
INSTANCE_CAN_START_STATES = [INSTANCE.REGISTERED, INSTANCE.STOPPED, INSTANCE.SUSPENDED]
INSTANCE_WAITING_STATES = [INSTANCE.REGISTERED]
INSTANCE_RUNNING_STATES = [INSTANCE.STARTING, INSTANCE.RUNNING]
INSTANCE_ERROR_STATES = [INSTANCE.ERROR, INSTANCE.DOWN]
INSTANCE_FINISHED_STATES = [INSTANCE.STOPPED, INSTANCE.DEREGISTERED]

# Possible version states.
VERSION = Enum(['NEW', 'PREPARED', 'READY', 'RUNNING'])

# The possible service states.
SERVICE = Enum(['NEW', 'AVAILABLE', 'ERROR', 'DELETED'])

# Various classes of service states.
SERVICE_ACTIVE_STATES = [SERVICE.AVAILABLE]
SERVICE_ERROR_STATES = [SERVICE.ERROR]

# Available permissions.
PERMISSION = Enum([
	'USER_LIST',
	'USER_EDIT',
	'ROLE_LIST',
	'ROLE_EDIT',
	'ROLE_ASSIGN',
	'WORKSPACE_EDIT',
	'WORKSPACE_LIST',
	'WORKSPACE_VIEW',
	'WORKSPACE_DELETE',
	'JOB_ABORT',
	'FILE_UPLOAD',
	'APPLICATION_CREATE',
	'APPLICATION_DEPLOY',
	'APPLICATION_DELETE',
	'APPLICATION_ROUTING',
	'SERVICE_VIEW',
	'SERVICE_CREDENTIAL_VIEW',
	'SERVICE_EXPORT',
	'SERVICE_IMPORT',
	'SERVICE_TUNNEL',
	'APPLICATION_VIEW_MANIFEST',
	'NODE_LIST',
	'NODE_DETAIL_VIEW',
	'SYSTEM_ADMINISTRATION',
	'SYSTEM_OVERVIEW',
	'HEALTH_CHECK'
])

HEALTH = Enum(['OK', 'WARNING', 'ERROR'])

# The possible node states.
NODE_STATES = ['ACTIVE', 'STOPPED', 'ERROR', 'INACTIVE']

# Various classes of node states.
NODE_ACTIVE_STATES = ['ACTIVE']
NODE_ERROR_STATES = ['ERROR']
NODE_STOPPED_STATES = ['STOPPED', 'ERROR']

# The possible job states.
JOB_STATES = ['NEW', 'WAITING', 'RUNNING', 'FAILED', 'ABORTED', 'SUCCESS']

# Various classes of job states.
JOB_RUNNING_STATES = ['NEW', 'WAITING', 'RUNNING']
JOB_SUCCESS_STATES = ['SUCCESS']
JOB_ERROR_STATES = ['FAILED', 'ABORTED']
JOB_FINISHED_STATES = ['ABORTED', 'SUCCESS', 'FAILED']

# The possible instance states.
INSTANCE_STATES = ['STARTING', 'RUNNING', 'STOPPED', 'ERROR', 'SHUTDOWN']

# Various classes of instance states.
INSTANCE_RUNNING_STATES = ['STARTING', 'RUNNING']
INSTANCE_ERROR_STATES = ['ERROR']
INSTANCE_FINISHED_STATES = ['STOPPED', 'SHUTDOWN']

# The possible instance type states.
INSTANCE_TYPE_STATES = ['NEW', 'PREPARED', 'ERROR', 'READY']

# Various classes of instance type states.
INSTANCE_TYPE_ERROR_STATES = ['ERROR']
INSTANCE_TYPE_READY_STATES = ['READY']

# The possible service states.
SERVICE_STATES = ['NEW', 'AVAILABLE', 'ERROR', 'DELETED']

# Various classes of service states.
SERVICE_ACTIVE_STATES = ['AVAILABLE']
INSTANCE_ERROR_STATES = ['ERROR']

#!/usr/bin/env python

#
# Paasmaker - Platform as a Service
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#

import sys
import os
import json
import time

# Check our current directory. Many things expect to be in the path
# of the server file, so switch directory if we need to.
paasmaker_home = os.path.dirname(os.path.abspath(__file__))
previous_cwd = os.getcwd()
if paasmaker_home != os.getcwd():
	# Make the current directory the one where the script is.
	os.chdir(paasmaker_home)

if not os.path.exists("thirdparty/python/bin/pip"):
	print "virtualenv not installed. Run install.py to set up this directory properly."
	sys.exit(1)

# Activate the environment now, inside this script.
bootstrap_script = "thirdparty/python/bin/activate_this.py"
execfile(bootstrap_script, dict(__file__=bootstrap_script))

# Internal imports.
import paasmaker
from paasmaker.common.core import constants

# External library imports.
import tornado.ioloop
import argparse
import yaml

# Logging setup.
import logging
logging.basicConfig(format='%(asctime)s %(levelname)s %(message)s', level=logging.INFO, stream=sys.stderr)

# Change the CWD back, as you might have specified a file to upload
# relative to where you currently are.
if previous_cwd != os.getcwd():
	os.chdir(previous_cwd)

# TODO: Write tests for all the actions in this file. Integration tests might cover this off
# though? But need to make sure we have appropriate coverage.

# This context wrapper handles exceptions that occur in callbacks, and
# causes the process to exit.
@tornado.stack_context.contextlib.contextmanager
def die_on_error():
	try:
		yield
	except Exception:
		logging.error("exception in asynchronous operation", exc_info=True)
		sys.exit(1)

class RootAction(object):
	def options(self, parser):
		# Define your options here.
		pass

	def process(self):
		self.exit()

	def describe(self):
		return "No description supplied."

	def _format_human(self, data):
		# The default format is to return in Yaml, it's
		# moderately nice to look at.
		return self._format_yaml(data)

	def _format_json(self, data):
		return json.dumps(data, indent=4, sort_keys=True)

	def _format_yaml(self, data):
		return yaml.safe_dump(data, default_flow_style=False, explicit_start=True, explicit_end=True)

	def prettyprint(self, data):
		if self.args.format == 'json':
			print self._format_json(data)
		elif self.args.format == 'yaml':
			print self._format_yaml(data)
		else:
			result = self._format_human(data)
			if result:
				print result

	def exit(self, code):
		tornado.ioloop.IOLoop.instance().stop()
		sys.exit(code)

	def point_and_auth(self, apirequest):
		host = "%s:%d" % (self.args.remote, self.args.port)
		apirequest.set_target(host)
		apirequest.set_auth(self.args.key)
		if self.args.ssl:
			apirequest.set_https()

	def generic_request_failed(self, message, exception=None):
		logging.error(message)
		if exception:
			logging.error(exception)
		self.exit(1)

	def generic_api_response_check_failed(self, response):
		if not response.success:
			self.generic_api_response(response)

	def generic_api_response(self, response):
		if response.success:
			logging.info("Successfully executed request.")
			# TODO: Handle warnings.
			self.prettyprint(response.data)
			sys.exit(0)
		else:
			logging.error("Request failed.")
			for error in response.errors:
				logging.error(error)
			if 'input_errors' in response.data:
				for field, error in response.data['input_errors'].iteritems():
					logging.error("- %s: %s", field, error)

			self.prettyprint(response.data)
			self.exit(1)

	def _follow(self, request):
		request.send(self._submit_complete)

	def _submit_complete(self, response):
		if response.success:
			logging.info("Successfully executed request.")
			# TODO: Handle warnings.
			self.prettyprint(response.data)
			# Now follow the submitted job.
			self._follow_job(response.data['job_id'])
		else:
			logging.error("Request failed.")
			for error in response.errors:
				logging.error(error)
			# TODO: Print errors in JSON format.
			self.prettyprint(response.data)
			self.exit(1)

	def _on_job_status(self, job_id, job_data):
		if self.args.format == 'json' or self.args.format == 'yaml':
			self.prettyprint(job_data)
		else:
			# Format nicely.
			if 'summary' in job_data:
				print "Job '%s' (%s) reached status %s (%s)." % (job_data['title'], job_id, job_data['state'], job_data['summary'])
			else:
				print "Job '%s' (%s) reached status %s." % (job_data['title'], job_id, job_data['state'])

		if job_data['job_id'] == self.job_id and job_data['state'] in constants.JOB_FINISHED_STATES:
			self._exit_on_job_state(job_data['state'])

	def _on_job_tree(self, job_id, tree):
		# See if the job tree has already finished.
		# If so, print it, and exit appropriately.
		if tree['state'] in constants.JOB_FINISHED_STATES:
			self.prettyprint(tree)
			self._exit_on_job_state(tree['state'])
		else:
			# Nothing to do - keep reading status updates until completion.
			pass

	def _exit_on_job_state(self, state):
		if state == constants.JOB.SUCCESS:
			logging.info("Completed successfully.")
			self.exit(0)
		else:
			logging.error("Failed to complete job.")
			self.exit(1)

	def _sink_event(self, *args):
		pass

	def _follow_job(self, job_id):
		def on_error(error):
			logging.error(error)
			self.exit(1)

		# Follow the rabbit hole...
		self.client = paasmaker.common.api.job.JobStreamAPIRequest(None)
		self.point_and_auth(self.client)
		self.client.set_error_callback(on_error)
		self.client.set_status_callback(self._on_job_status)
		self.client.set_tree_callback(self._on_job_tree)
		self.client.set_new_callback(self._sink_event)
		self.client.set_subscribed_callback(self._sink_event)
		self.client.subscribe(job_id)
		self.client.connect()

		self.job_id = job_id

	def _stream_error_callback(self, message):
		logging.error(message)
		self.exit(1)

class UserCreateAction(RootAction):
	def options(self, parser):
		parser.add_argument("login", help="User login name")
		parser.add_argument("email", help="Email address")
		parser.add_argument("name", help="User name")
		parser.add_argument("password", help="Password")

	def describe(self):
		return "Create a user."

	def process(self):
		request = paasmaker.common.api.user.UserCreateAPIRequest(None)
		request.set_user_params(self.args.name, self.args.login, self.args.email, True)
		request.set_user_password(self.args.password)
		self.point_and_auth(request)
		request.send(self.generic_api_response)

	def _format_human(self, data):
		if 'user' in data and data['user']['id']:
			return "Created new user ID %d, login %s." % (data['user']['id'], data['user']['login'])

class UserEditAction(RootAction):
	def options(self, parser):
		parser.add_argument("user_id", help="User ID to edit")
		parser.add_argument("--name", type=str, default=None, help="The name of the user.")
		parser.add_argument("--email", type=str, default=None, help="The email of the user.")
		parser.add_argument("--login", type=str, default=None, help="The login of the user.")
		parser.add_argument("--password", type=str, default=None, help="The password of the user.")

	def describe(self):
		return "Edit a user."

	def process(self):
		def user_loaded(roledata):
			if self.args.name:
				request.set_user_name(self.args.name)
			if self.args.login:
				request.set_user_login(self.args.login)
			if self.args.email:
				request.set_user_email(self.args.email)
			if self.args.password:
				request.set_user_password(self.args.password)
			request.send(self.generic_api_response)

		request = paasmaker.common.api.user.UserEditAPIRequest(None)
		self.point_and_auth(request)
		request.load(int(self.args.user_id), user_loaded, self.generic_request_failed)

	def _format_human(self, data):
		if 'user' in data and data['user']['id']:
			return "Updated user ID %d, login %s." % (data['user']['id'], data['user']['login'])

class UserGetAction(RootAction):
	def options(self, parser):
		parser.add_argument("user_id", help="User ID to fetch")

	def describe(self):
		return "Get a user record."

	def process(self):
		request = paasmaker.common.api.user.UserGetAPIRequest(None)
		request.set_user(int(self.args.user_id))
		self.point_and_auth(request)
		request.send(self.generic_api_response)

	# Formatting: use the YAML output which is the default.

class UserListAction(RootAction):
	def describe(self):
		return "List users."

	def process(self):
		request = paasmaker.common.api.user.UserListAPIRequest(None)
		self.point_and_auth(request)
		request.send(self.generic_api_response)

	def _format_human(self, data):
		if 'users' in data:
			result = ""
			result += "Found %d users.\n" % len(data['users'])
			for user in data['users']:
				result += self._format_yaml(user)

			return result

class UserEnableAction(RootAction):
	ENABLE = True

	def options(self, parser):
		parser.add_argument("user_id", help="User ID to change.")

	def describe(self):
		if self.ENABLE:
			return "Enable a user."
		else:
			return "Disable a user."

	def process(self):
		request = paasmaker.common.api.user.UserEditAPIRequest(None)

		def user_loaded(response):
			request.set_user_enabled(self.ENABLE)
			request.send(self.generic_api_response)

		self.point_and_auth(request)
		request.load(int(self.args.user_id), user_loaded, self.generic_request_failed)

	def _format_human(self, data):
		if 'user' in data and data['user']['id']:
			if self.ENABLE:
				return "User ID %d was enabled." % data['user']['id']
			else:
				return "User ID %d was disabled." % data['user']['id']

class UserDisableAction(UserEnableAction):
	ENABLE = False

class RoleCreateAction(RootAction):
	def options(self, parser):
		parser.add_argument("name", help="Role name")
		parser.add_argument("permissions", help="Comma seperated list of permissions")

	def describe(self):
		return "Create a role."

	def process(self):
		permissions = self.args.permissions.replace(" ", "").split(",")

		request = paasmaker.common.api.role.RoleCreateAPIRequest(None)
		request.set_role_params(self.args.name, permissions)
		self.point_and_auth(request)
		request.send(self.generic_api_response)

	def _format_human(self, data):
		if 'role' in data and data['role']['id']:
			result = "Created new role ID %d, name '%s'." % (data['role']['id'], data['role']['name'])
			result += "\nPermissions: %s" % data['role']['permissions']

			return result

class RoleEditAction(RootAction):
	def options(self, parser):
		parser.add_argument("role_id", help="Role ID to edit")
		parser.add_argument("--name", type=str, default=None, help="The name of the role.")
		parser.add_argument("--permissions", type=str, default=None, help="The permissions assigned to the role. Replaces all the permissions with the set provided.")

	def describe(self):
		return "Edit a role."

	def process(self):
		def role_loaded(roledata):
			if self.args.name:
				request.set_role_name(self.args.name)
			if self.args.permissions:
				permissions = self.args.permissions.replace(" ", "").split(",")
				request.set_role_permissions(permissions)
			request.send(self.generic_api_response)

		request = paasmaker.common.api.role.RoleEditAPIRequest(None)
		self.point_and_auth(request)
		request.load(int(self.args.role_id), role_loaded, self.generic_request_failed)

	def _format_human(self, data):
		if 'role' in data and data['role']['id']:
			result = "Edited role ID %d, name '%s'." % (data['role']['id'], data['role']['name'])
			result += "\nPermissions: %s" % data['role']['permissions']

			return result

class RoleGetAction(RootAction):
	def options(self, parser):
		parser.add_argument("role_id", help="Role ID to fetch")

	def describe(self):
		return "Get a role record."

	def process(self):
		request = paasmaker.common.api.role.RoleGetAPIRequest(None)
		request.set_role(int(self.args.role_id))
		self.point_and_auth(request)
		request.send(self.generic_api_response)

class RoleListAction(RootAction):
	def describe(self):
		return "List roles."

	def process(self):
		request = paasmaker.common.api.role.RoleListAPIRequest(None)
		self.point_and_auth(request)
		request.send(self.generic_api_response)

	def _format_human(self, data):
		if 'roles' in data:
			result = ""
			result += "Found %d roles.\n" % len(data['roles'])
			for role in data['roles']:
				result += self._format_yaml(role)

			return result

class RoleAllocationListAction(RootAction):
	def describe(self):
		return "List role allocations."

	def process(self):
		request = paasmaker.common.api.role.RoleAllocationListAPIRequest(None)
		self.point_and_auth(request)
		request.send(self.generic_api_response)

	def _format_human(self, data):
		if 'allocations' in data:
			result = ""
			result += "Found %d allocations.\n" % len(data['allocations'])
			for allocation in data['allocations']:
				result += self._format_yaml(allocation)

			return result

class RoleAllocationAction(RootAction):
	def options(self, parser):
		parser.add_argument("role_id", type=int, help="Role ID to assign")
		parser.add_argument("user_id", type=int, help="User ID to assign")
		parser.add_argument("--workspace_id", type=int, help="Workspace ID to assign (optional)", default=None)

	def describe(self):
		return "Allocate a role to a user and workspace."

	def process(self):
		request = paasmaker.common.api.role.RoleAllocationAPIRequest(None)
		workspace_id = None
		if self.args.workspace_id:
			workspace_id = int(self.args.workspace_id)
		request.set_allocation_params(int(self.args.user_id), int(self.args.role_id), workspace_id)
		self.point_and_auth(request)
		request.send(self.generic_api_response)

	def _format_human(self, data):
		if 'allocation' in data:
			if data['allocation']['workspace']:
				result = "Allocated role '%s' (ID %d) to user '%s' (ID %d), for workspace '%s' (ID %d)" % (
					data['allocation']['role']['name'],
					data['allocation']['role']['id'],
					data['allocation']['user']['login'],
					data['allocation']['user']['id'],
					data['allocation']['workspace']['name'],
					data['allocation']['workspace']['id']
				)
			else:
				result = "Allocated role '%s' (ID %d) to user '%s' (ID %d), applied globally." % (
					data['allocation']['role']['name'],
					data['allocation']['role']['id'],
					data['allocation']['user']['login'],
					data['allocation']['user']['id']
				)
			return result

class RoleUnAllocateAction(RootAction):
	def options(self, parser):
		parser.add_argument("allocation_id", help="Allocation to remove.")

	def describe(self):
		return "Remove a role allocation."

	def process(self):
		request = paasmaker.common.api.role.RoleUnAllocationAPIRequest(None)
		request.set_allocation_id(int(self.args.allocation_id))
		self.point_and_auth(request)
		request.send(self.generic_api_response)

	def _format_human(self, data):
		if 'success' in data:
			return "Unallocated role."

class WorkspaceCreateAction(RootAction):
	def options(self, parser):
		parser.add_argument("name", help="Workspace name")
		parser.add_argument("stub", help="Workspace stub")
		parser.add_argument("tags", help="JSON formatted tags for this workspace.", default="{}")

	def describe(self):
		return "Create a workspace."

	def process(self):
		tags = json.loads(self.args.tags)

		request = paasmaker.common.api.workspace.WorkspaceCreateAPIRequest(None)
		request.set_workspace_name(self.args.name)
		request.set_workspace_stub(self.args.stub)
		request.set_workspace_tags(tags)
		self.point_and_auth(request)
		request.send(self.generic_api_response)

	def _format_human(self, data):
		if 'workspace' in data:
			return "Created workspace '%s' (ID %d)." % (data['workspace']['name'], data['workspace']['id'])

class WorkspaceEditAction(RootAction):
	def options(self, parser):
		parser.add_argument("workspace_id", help="Workspace ID to edit")
		parser.add_argument("--name", type=str, default=None, help="The name of the workspace.")
		parser.add_argument("--stub", type=str, default=None, help="The stub of the workspace.")
		parser.add_argument("--tags", type=str, default=None, help="JSON formatted tags for this workspace.")

	def describe(self):
		return "Edit a workspace."

	def process(self):
		def workspace_loaded(roledata):
			if self.args.name:
				request.set_workspace_name(self.args.name)
			if self.args.tags:
				tags = json.loads(self.args.tags)
				request.set_workspace_tags(tags)
			if self.args.stub:
				request.set_workspace_stub(self.args.stub)
			request.send(self.generic_api_response)

		request = paasmaker.common.api.workspace.WorkspaceEditAPIRequest(None)
		self.point_and_auth(request)
		request.load(int(self.args.workspace_id), workspace_loaded, self.generic_request_failed)

	def _format_human(self, data):
		if 'workspace' in data:
			return "Edited workspace '%s' (ID %d)." % (data['workspace']['name'], data['workspace']['id'])

class WorkspaceGetAction(RootAction):
	def options(self, parser):
		parser.add_argument("workspace_id", help="Workspace ID to fetch")

	def describe(self):
		return "Get a workspace record."

	def process(self):
		request = paasmaker.common.api.workspace.WorkspaceGetAPIRequest(None)
		request.set_workspace(int(self.args.workspace_id))
		self.point_and_auth(request)
		request.send(self.generic_api_response)

	# Use the default yaml format.

class WorkspaceListAction(RootAction):
	def describe(self):
		return "List workspaces."

	def process(self):
		request = paasmaker.common.api.workspace.WorkspaceListAPIRequest(None)
		self.point_and_auth(request)
		request.send(self.generic_api_response)

	def _format_human(self, data):
		if 'workspaces' in data:
			result = ""
			result += "Found %d workspaces.\n" % len(data['workspaces'])
			for workspace in data['workspaces']:
				result += self._format_yaml(workspace)

			return result

class WorkspaceDeleteAction(RootAction):
	def options(self, parser):
		parser.add_argument("workspace_id", help="Workspace ID to delete")

	def describe(self):
		return "Delete a workspace."

	def process(self):
		request = paasmaker.common.api.workspace.WorkspaceDeleteAPIRequest(None)
		request.set_workspace(int(self.args.workspace_id))
		self.point_and_auth(request)
		request.send(self.generic_api_response)

	def _format_human(self, data):
		if 'workspace' in data:
			return "Deleted workspace '%s' (ID %d)." % (data['workspace']['name'], data['workspace']['id'])

class NodeListAction(RootAction):
	def describe(self):
		return "List nodes."

	def process(self):
		request = paasmaker.common.api.nodelist.NodeListAPIRequest(None)
		self.point_and_auth(request)
		request.send(self.generic_api_response)

	def _format_human(self, data):
		if 'nodes' in data:
			result = ""
			result += "Found %d nodes.\n" % len(data['nodes'])
			for node in data['nodes']:
				result += self._format_yaml(node)

			return result

class FileUploadAction(RootAction):
	def options(self, parser):
		parser.add_argument("filename", help="The filename to upload.")

	def describe(self):
		return "Upload a file to the server. NOTE: Must use user authentication."

	def _progress(self, position, total):
		percent = (float(position) / float(total)) * 100;
		logger.info("%d bytes of %d uploaded (%.2f%%).", position, total, percent)

	def _finished(self, data):
		self.prettyprint(data['data'])
		self.exit(0)

	def _error(self, message):
		self.prettyprint(message)
		self.exit(1)

	def process(self):
		# TODO: This times out on large files, waiting for the server to assemble them.
		request = paasmaker.common.api.upload.UploadFileAPIRequest(None)
		self.point_and_auth(request)
		request.send_file(
			self.args.filename,
			self._progress,
			self._finished,
			self._error
		)

	def _format_human(self, data):
		if 'identifier' in data:
			return "Uploaded file, identifier: %s" % data['identifier']

class ApplicationGetAction(RootAction):
	def options(self, parser):
		parser.add_argument("application_id", help="Application ID to fetch")

	def describe(self):
		return "Get an application record."

	def process(self):
		request = paasmaker.common.api.application.ApplicationGetAPIRequest(None)
		request.set_application(int(self.args.application_id))
		self.point_and_auth(request)
		request.send(self.generic_api_response)

	def _format_human(self, data):
		if 'application' in data:
			return self._format_yaml({'application': data['application']})

class ApplicationDeleteAction(RootAction):
	def options(self, parser):
		parser.add_argument("application_id", help="Application ID to delete")
		parser.add_argument("--follow", default=False, help="Follow the progress of this job.", action="store_true")

	def describe(self):
		return "Deletes an application (which must not have versions in ready or running state)"

	def process(self):
		request = paasmaker.common.api.application.ApplicationDeleteAPIRequest(None)
		request.set_application(int(self.args.application_id))
		self.point_and_auth(request)
		self.args = args
		if self.args.follow:
			self._follow(request)
		else:
			request.send(self.generic_api_response)

	def _format_human(self, data):
		if 'job_id' in data:
			return "Submitted delete job %s." % (data['job_id'])

class ApplicationListAction(RootAction):
	def options(self, parser):
		parser.add_argument("workspace_id", help="Workspace ID to list")

	def describe(self):
		return "List applications in the given workspace."

	def process(self):
		request = paasmaker.common.api.application.ApplicationListAPIRequest(None)
		request.set_workspace(int(self.args.workspace_id))
		self.point_and_auth(request)
		request.send(self.generic_api_response)

	def _format_human(self, data):
		if 'applications' in data:
			result = ""
			result += "Found %d applications.\n" % len(data['applications'])
			for application in data['applications']:
				result += self._format_yaml(application)

			return result

class ApplicationVersionRootAction(RootAction):
	def options(self, parser):
		parser.add_argument("scm", help="The SCM plugin to handle this application.")
		parser.add_argument("--uploadedfile", help="The uploaded file.", default=None)
		parser.add_argument("--parameters", help="Other parameters for the SCM. Expects a JSON formatted string.", default={})
		parser.add_argument("--manifestpath", help="The path to the manifest file inside the SCM. Optional.", default=None)
		parser.add_argument("--follow", default=False, help="Follow the progress of this job.", action="store_true")

	def _set_common(self, request):
		request.set_scm(self.args.scm)
		if self.args.uploadedfile:
			request.set_uploaded_file(self.args.uploadedfile)
		if self.args.parameters:
			params = json.loads(self.args.parameters)
			request.set_parameters(params)
		if self.args.manifestpath:
			request.set_manifest_path(self.args.manifestpath)
		self.point_and_auth(request)

class ApplicationNewAction(ApplicationVersionRootAction):
	def options(self, parser):
		parser.add_argument("workspace_id", help="The workspace to place this application in.")
		super(ApplicationNewAction, self).options(parser)

	def describe(self):
		return "Create a new application."

	def process(self):
		request = paasmaker.common.api.application.ApplicationNewAPIRequest(None)
		request.set_workspace(int(self.args.workspace_id))
		self._set_common(request)
		if self.args.follow:
			self._follow(request)
		else:
			request.send(self.generic_api_response)

	def _format_human(self, data):
		if 'job_id' in data:
			return "Submitted new application job %s." % (data['job_id'])

class ApplicationNewVersionAction(ApplicationVersionRootAction):
	def options(self, parser):
		parser.add_argument("application_id", help="The application_id to create the new version for.")
		super(ApplicationNewVersionAction, self).options(parser)

	def describe(self):
		return "Create a new application version."

	def process(self):
		request = paasmaker.common.api.application.ApplicationNewVersionAPIRequest(None)
		request.set_application(int(self.args.application_id))
		self._set_common(request)
		if self.args.follow:
			self._follow(request)
		else:
			request.send(self.generic_api_response)

	def _format_human(self, data):
		if 'job_id' in data:
			return "Submitted new application job %s." % (data['job_id'])

class VersionGetAction(RootAction):
	def options(self, parser):
		parser.add_argument("version_id", help="Version ID to fetch")

	def describe(self):
		return "Get a version record."

	def process(self):
		request = paasmaker.common.api.version.VersionGetAPIRequest(None)
		request.set_version(int(self.args.version_id))
		self.point_and_auth(request)
		request.send(self.generic_api_response)

	# Use the default formatter.

class VersionInstancesAction(RootAction):
	def options(self, parser):
		parser.add_argument("version_id", help="Version ID to fetch")

	def describe(self):
		return "Get a list of instances for the given version."

	def process(self):
		request = paasmaker.common.api.version.VersionInstancesAPIRequest(None)
		request.set_version(int(self.args.version_id))
		self.point_and_auth(request)
		request.send(self.generic_api_response)

	# Use the default formatter.

class VersionRootAction(RootAction):
	def options(self, parser):
		parser.add_argument("version_id", help="Version ID to act upon.")
		parser.add_argument("--follow", default=False, help="Follow the progress of this job.", action="store_true")

	def _process(self, request):
		request.set_version(int(self.args.version_id))
		self.point_and_auth(request)
		if self.args.follow:
			self._follow(request)
		else:
			request.send(self.generic_api_response)

class VersionRegisterAction(VersionRootAction):
	def describe(self):
		return "Register the given version."

	def process(self):
		request = paasmaker.common.api.version.VersionRegisterAPIRequest(None)
		self._process(request)

	def _format_human(self, data):
		if 'job_id' in data:
			return "Submitted version registration job %s." % (data['job_id'])

class VersionStartAction(VersionRootAction):
	def describe(self):
		return "Start the given version."

	def process(self):
		request = paasmaker.common.api.version.VersionStartAPIRequest(None)
		self._process(request)

	def _format_human(self, data):
		if 'job_id' in data:
			return "Submitted version startup job %s." % (data['job_id'])

class VersionStopAction(VersionRootAction):
	def describe(self):
		return "Stop the given version."

	def process(self):
		request = paasmaker.common.api.version.VersionStopAPIRequest(None)
		self._process(request)

	def _format_human(self, data):
		if 'job_id' in data:
			return "Submitted version shutdown job %s." % (data['job_id'])

class VersionDeRegisterAction(VersionRootAction):
	def describe(self):
		return "De register the given version."

	def process(self):
		request = paasmaker.common.api.version.VersionDeRegisterAPIRequest(None)
		self._process(request)

	def _format_human(self, data):
		if 'job_id' in data:
			return "Submitted version de-registration job %s." % (data['job_id'])

class VersionSetCurrentAction(VersionRootAction):
	def describe(self):
		return "Makes the selected version current."

	def process(self):
		request = paasmaker.common.api.version.VersionSetCurrentAPIRequest(None)
		self._process(request)

	def _format_human(self, data):
		if 'job_id' in data:
			return "Submitted version make current job %s." % (data['job_id'])

class VersionDeleteAction(RootAction):
	def options(self, parser):
		parser.add_argument("version_id", help="Version ID to delete")

	def describe(self):
		return "Delete the given version."

	def process(self):
		request = paasmaker.common.api.version.VersionDeleteAPIRequest(None)
		request.set_version(int(self.args.version_id))
		self.point_and_auth(request)
		request.send(self.generic_api_response)

	def _format_human(self, data):
		if 'version' in data:
			return "Deleted version %d (ID %d)." % (data['version']['version'], data['version']['id'])

class JobAbortAction(RootAction):
	def options(self, parser):
		parser.add_argument("job_id", help="Job ID to abort")

	def describe(self):
		return "Abort a given job and it's related job tree."

	def process(self):
		request = paasmaker.common.api.job.JobAbortAPIRequest(None)
		request.set_job(self.args.job_id)
		self.point_and_auth(request)
		request.send(self.generic_api_response)

	def _format_human(self, data):
		if 'job_id' in data:
			return "Aborted job %d" % data['job_id']

class JobFollowAction(RootAction):
	def options(self, parser):
		parser.add_argument("job_id", help="Job ID to follow")

	def describe(self):
		return "Follows a job. Exits when the root job reaches a completed status. Exits with 0 on success, or 1 on failure."

	def process(self):
		self.args = args
		self._follow_job(self.args.job_id)

class RouterTableDumpAction(RootAction):
	def describe(self):
		return "Dump all the entries in the router table."

	def process(self):
		request = paasmaker.common.api.router.RouterTableDumpAPIRequest(None)
		self.point_and_auth(request)
		request.send(self.generic_api_response)

	def _format_human(self, data):
		postfix = ""
		result = ""
		if 'frontend_domain_postfix' in data:
			postfix = data['frontend_domain_postfix']
		if 'serial' in data:
			result += "Table serial number: %s\n" % data['serial']
		if 'table' in data:
			for entry in data['table']:
				result += "For http://%s%s :\n" % (entry['hostname'], postfix)
				result += " %d nodes\n" % len(entry['nodes'])
				if len(entry['nodes']) > 0:
					for node in entry['nodes']:
						result += "   Node '%s' (%s, ID %d)\n" % (node['name'], node['uuid'], node['id'])

				result += " %d instances\n" % len(entry['instances'])
				if len(entry['instances']) > 0:
					for instance in entry['instances']:
						result += "   Instance %s, state %s, node %s.\n" % (instance['instance_id'], instance['state'], instance['node_id'])

				result += " %d routes\n" % len(entry['routes'])
				for route in entry['routes']:
					result += "   Route: %s\n" % route

		return result

class RouterStreamAction(RootAction):
	def options(self, parser):
		parser.add_argument("name", help="Name of stats to stream, eg 'workspace'")
		parser.add_argument("input_id", help="ID value of stats to stream, eg '1'")

	def describe(self):
		return "Streams router stats, once per second. For example, pass 'workspace 1' as the arguments to stream stats for the first workspace."

	def process(self):
		logger.info("** Press CTRL+C to cancel.")
		request = paasmaker.common.api.router.RouterStreamAPIRequest(None)
		request.set_error_callback(self._stream_error_callback)
		self.point_and_auth(request)

		def request_stats():
			request.stats(self.args.name, self.args.input_id)

		def on_stats(name, input_id, stats):
			self.prettyprint(stats)
			tornado.ioloop.IOLoop.instance().add_timeout(time.time() + 1, request_stats)

		def on_error(message, exception=None, name=None, input_id=None):
			logger.error(message)
			self.exit(1)

		request.set_update_callback(on_stats)
		request.set_stats_error_callback(on_error)
		request.connect()

		request_stats()

class LogStreamAction(RootAction):
	def options(self, parser):
		parser.add_argument("job_id", help="Job ID to stream")
		parser.add_argument("--position", default=0, help="Only return the log since this position.")

	def describe(self):
		return "Stream the given job ID."

	def process(self):
		logger.info("** Press CTRL+C to cancel.")
		request = paasmaker.common.api.log.LogStreamAPIRequest(None)
		request.set_error_callback(self._stream_error_callback)
		self.point_and_auth(request)

		def on_message(job_id, lines, position):
			print "".join(lines),

		def on_error(job_id, error):
			logger.error(error)
			self.exit(1)

		request.set_lines_callback(on_message)
		request.set_cantfind_callback(on_error)
		request.subscribe(self.args.job_id, position=self.args.position)
		request.connect()

class HelpAction(RootAction):
	def options(self, parser):
		pass

	def process(self):
		help_keys = ACTION_MAP.keys()
		help_keys.sort()
		for key in help_keys:
			logging.info("%s: %s", key, ACTION_MAP[key].describe())

		self.exit(0)

	def describe(self):
		return "Show a list of actions."

# Peek ahead at the command line options for the main action.
if len(sys.argv) == 1:
	# Nothing supplied.
	print "No module supplied. Usage: %s action" % sys.argv[0]
	print "Try %s help" % sys.argv[0]
	sys.exit(1)

action = sys.argv[1]

ACTION_MAP = {
	'user-create': UserCreateAction(),
	'user-edit': UserEditAction(),
	'user-get': UserGetAction(),
	'user-list': UserListAction(),
	'user-enable': UserEnableAction(),
	'user-disable': UserDisableAction(),
	'role-create': RoleCreateAction(),
	'role-edit': RoleEditAction(),
	'role-get': RoleGetAction(),
	'role-list': RoleListAction(),
	'workspace-create': WorkspaceCreateAction(),
	'workspace-edit': WorkspaceEditAction(),
	'workspace-get': WorkspaceGetAction(),
	'workspace-list': WorkspaceListAction(),
	'workspace-delete': WorkspaceDeleteAction(),
	'node-list': NodeListAction(),
	'role-allocation-list': RoleAllocationListAction(),
	'role-allocate': RoleAllocationAction(),
	'role-unallocate': RoleUnAllocateAction(),
	'file-upload': FileUploadAction(),
	'application-get': ApplicationGetAction(),
	'application-list': ApplicationListAction(),
	'application-new': ApplicationNewAction(),
	'application-newversion': ApplicationNewVersionAction(),
	'application-delete': ApplicationDeleteAction(),
	'version-get': VersionGetAction(),
	'version-instances': VersionInstancesAction(),
	'version-register': VersionRegisterAction(),
	'version-start': VersionStartAction(),
	'version-stop': VersionStopAction(),
	'version-deregister': VersionDeRegisterAction(),
	'version-setcurrent': VersionSetCurrentAction(),
	'version-delete': VersionDeleteAction(),
	'job-abort': JobAbortAction(),
	'job-follow': JobFollowAction(),
	'log-stream': LogStreamAction(),
	'router-table-dump': RouterTableDumpAction(),
	'router-stream': RouterStreamAction(),
	'help': HelpAction(),
	'--help': HelpAction()
}

# If there is no action...
if not ACTION_MAP.has_key(action):
	print "No such action %s. Try %s help" % (action, sys.argv[0])
	sys.exit(1)

# Shortcut to show help, and prevent an error when trying to parse
# other required arguments.
if action == 'help' or action == '--help':
	ACTION_MAP['help'].process()
	sys.exit(0)

# Set up our parser.
parser = argparse.ArgumentParser()
parser.add_argument('action', help="The action to perform.")

# Set up common command line options.
parser.add_argument("-r", "--remote", default="localhost", help="The pacemaker host.")
parser.add_argument("-p", "--port", type=int, default=42500, help="The pacemaker port.")
parser.add_argument("-k", "--key", help="Key to authenticate with. Either a user API key, or a super token.")
parser.add_argument("--ssl", default=False, help="Use SSL to connect to the node.", action="store_true")
parser.add_argument("--loglevel", default="INFO", help="Log level, one of DEBUG|INFO|WARNING|ERROR|CRITICAL.")
parser.add_argument("--format", default="human", help="Output format, either 'json', 'yaml', or 'human'")

# Now get our action to set up it's options.
ACTION_MAP[action].options(parser)

# Parse all the arguments.
args = parser.parse_args()

# Reset the log level.
logging.debug("Resetting log level to %s.", args.loglevel)
logger = logging.getLogger()
logger.setLevel(getattr(logging, args.loglevel))

logger.debug("Parsed command line arguments: %s", str(args))

# Make sure we have an auth source.
if not args.key:
	logger.error("No API or node key passed.")
	sys.exit(1)

# Now we wait for the IO loop to start before starting.
def on_start():
	# And wrap anything in a stack context to handle errors.
	with tornado.stack_context.StackContext(die_on_error):
		instance = ACTION_MAP[action]
		instance.args = args
		instance.process()

# Commence the application.
if __name__ == "__main__":
	# Start the loop.
	try:
		tornado.ioloop.IOLoop.instance().add_callback(on_start)
		tornado.ioloop.IOLoop.instance().start()
		logging.debug("Exiting.")
	except Exception, ex:
		# Catch all, to catch things thrown in the callbacks.
		logging.error(ex)
		tornado.ioloop.IOLoop.instance().stop()

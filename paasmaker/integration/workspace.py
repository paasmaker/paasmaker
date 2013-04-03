#
# Paasmaker - Platform as a Service
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#

import uuid

import paasmaker

class WorkspaceIntegrationTest(paasmaker.common.testhelpers.BaseMultipaasTest):

	def test_simple(self):
		self.add_multipaas_node(pacemaker=True, heart=True, router=True)
		self.start_multipaas(self.stop)
		self.wait()

		with paasmaker.common.testhelpers.MultipaasTestHandler(self):
			# The starter would have created a workspace.
			# Edit that workspace.
			edited_workspace_name = str(uuid.uuid4())
			edited_workspace_stub = edited_workspace_name.replace("-", '')

			self.execute(
				[
					'workspace-edit',
					self.mp_workspace_id,
					'--name', edited_workspace_name,
					'--stub', edited_workspace_stub,
					'--tags', '{"test":"tag"}'
				]
			)

			# Fetch it out again.
			self.execute(
				[
					'workspace-get',
					self.mp_workspace_id
				]
			)

			workspace = self.data

			self.assertEquals(workspace['workspace']['name'], edited_workspace_name, "Did not set workspace name.")
			self.assertEquals(workspace['workspace']['stub'], edited_workspace_stub, "Did not set workspace stub.")
			self.assertTrue("test" in workspace['workspace']['tags'], "Did not set tags correctly.")
			self.assertEquals(workspace['workspace']['tags']['test'], 'tag', "Did not set tag value.")

			# Now try to create a new workspace.
			new_workspace_name = str(uuid.uuid4())
			new_workspace_stub = new_workspace_name.replace("-", '')

			self.execute(
				[
					'workspace-create',
					new_workspace_name,
					new_workspace_stub,
					'{"test":"tag"}'
				]
			)

			new_workspace = self.data
			new_workspace_id = new_workspace['workspace']['id']

			# Fetch it out again.
			self.execute(
				[
					'workspace-get',
					new_workspace['workspace']['id']
				]
			)

			workspace = self.data

			self.assertEquals(workspace['workspace']['name'], new_workspace_name, "Did not set workspace name.")
			self.assertEquals(workspace['workspace']['stub'], new_workspace_stub, "Did not set workspace stub.")
			self.assertTrue("test" in workspace['workspace']['tags'], "Did not set tags correctly.")
			self.assertEquals(workspace['workspace']['tags']['test'], 'tag', "Did not set tag value.")

			# Try to edit the second workspace to have the same name as the first.
			self.execute(
				[
					'workspace-edit',
					new_workspace_id,
					'--name', edited_workspace_name,
					'--stub', edited_workspace_stub,
					'--tags', '{"test":"tag"}'
				],
				assert_success=False
			)

			self.assertFalse(self.success, "Should not have succeeded.")
			self.assertIn("not unique", self.errors)

			# Apply the role directly to the new workspace.
			self.execute(
				[
					'role-allocate',
					self.mp_role_id,
					self.mp_user_id,
					'--workspace_id', new_workspace_id
				]
			)

			# Fetch the list of allocations.
			self.execute(
				[
					'role-allocation-list'
				]
			)

			self.assertEquals(len(self.data['allocations']), 2, "Wrong number of role allocations.")

			# Delete the workspace.
			self.execute(
				[
					'workspace-delete',
					new_workspace_id
				]
			)
			self.execute(
				[
					'workspace-delete',
					self.mp_workspace_id
				]
			)

			# Now only one role allocation should exist; they should have cascade deleted from the database.
			self.execute(
				[
					'role-allocation-list'
				]
			)

			self.assertEquals(len(self.data['allocations']), 1, "Wrong number of role allocations.")
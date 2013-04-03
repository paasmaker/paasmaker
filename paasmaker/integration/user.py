#
# Paasmaker - Platform as a Service
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#

import uuid

import paasmaker

class UserIntegrationTest(paasmaker.common.testhelpers.BaseMultipaasTest):

	def test_simple(self):
		self.add_multipaas_node(pacemaker=True, heart=True, router=True)
		self.start_multipaas(self.stop)
		self.wait()

		with paasmaker.common.testhelpers.MultipaasTestHandler(self):
			# Create a new user.

			# Firstly, try to create a user under the password length requirement.
			self.execute(
				[
					'user-create',
					'test',
					'test@bar.com',
					'Test',
					'short'
				],
				assert_success=False
			)

			self.assertFalse(self.success, "Succeeded when it should not have.")
			self.assertIn("Shorter than minimum length", self.errors, "Wrong error message.")

			# Create them again with a longer password.
			self.execute(
				[
					'user-create',
					'test',
					'test@bar.com',
					'Test',
					'longpassword'
				]
			)

			# Record their ID.
			test_user_id = self.data['user']['id']

			# Try to create another user with a duplicate email address.
			self.execute(
				[
					'user-create',
					'test2',
					'test@bar.com',
					'Test',
					'longpassword'
				],
				assert_success=False
			)

			self.assertFalse(self.success, "Succeeded when it should not have.")
			self.assertIn("email address is not unique", self.errors, "Wrong error message.")

			# Try to create another user with a duplicate login.
			self.execute(
				[
					'user-create',
					'test',
					'test2@bar.com',
					'Test',
					'longpassword'
				],
				assert_success=False
			)

			self.assertFalse(self.success, "Succeeded when it should not have.")
			self.assertIn("login name is not unique", self.errors, "Wrong error message.")

			# Disable the first user.
			self.execute(
				[
					'user-disable',
					self.mp_user_id
				]
			)

			self.execute(
				[
					'user-get',
					self.mp_user_id
				]
			)

			self.assertFalse(self.data['user']['enabled'], "User was still enabled.")

			# Enable them again.
			self.execute(
				[
					'user-enable',
					self.mp_user_id
				]
			)

			self.execute(
				[
					'user-get',
					self.mp_user_id
				]
			)

			self.assertTrue(self.data['user']['enabled'], "User was still disabled.")

			# List all the users. Should be two.
			self.execute(
				[
					'user-list'
				]
			)

			self.assertEquals(len(self.data['users']), 2, "Wrong number of users.")
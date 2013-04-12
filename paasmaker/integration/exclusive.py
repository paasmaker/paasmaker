#
# Paasmaker - Platform as a Service
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#

import uuid

import paasmaker

class ExclusiveInstanceIntegrationTest(paasmaker.common.testhelpers.BaseMultipaasTest):

	def test_simple(self):
		self.add_multipaas_node(pacemaker=True, heart=False, router=False)
		self.add_multipaas_node(pacemaker=False, heart=True, router=True)
		self.start_multipaas(self.stop)
		self.wait()

		with paasmaker.common.testhelpers.MultipaasTestHandler(self):
			# Prepare the sample application.
			application_tarball = self.pack_sample_application_local('exclusive-test')

			# We need to act as a user to upload a file, so switch to using the
			# API key auth.
			self.executor.switch_to_user_auth(self.mp_user_id, self.stop)
			self.wait()

			# Upload the file.
			self.execute(
				[
					'file-upload',
					application_tarball
				]
			)

			identifier = self.data['identifier']

			# Now create a new application from that uploaded file.
			self.execute(
				[
					'application-new',
					self.mp_workspace_id,
					'paasmaker.scm.tarball',
					'--uploadedfile', identifier
				]
			)

			# That would have returned a job ID. Follow it to completion.
			job_id = self.data['job_id']
			self.follow_job(job_id, timeout=10)
			self.assertTrue(self.success, "Create application job did not succeed.")

			# Fetch the version data.
			self.execute(
				[
					'application-list',
					self.mp_workspace_id
				]
			)

			application_id = self.data['applications'][0]['id']

			self.execute(
				[
					'application-get',
					application_id
				]
			)

			version_one_id = self.data['versions'][0]['id']

			# Start up that version.
			self.execute(
				[
					'version-start',
					version_one_id
				]
			)

			job_id = self.data['job_id']
			self.follow_job(job_id, timeout=10)
			self.assertTrue(self.success, "Version start job did not succeed.")

			# From that version, query out the instances.
			self.execute(
				[
					'version-instances',
					version_one_id
				]
			)

			# There should be one instance of the 'web' type and none of the
			# 'standalone' type.
			self.assertEquals(len(self.data['instances']['web']['instances']), 1, "Wrong number of 'web' instances.")
			self.assertEquals(len(self.data['instances']['standalone']['instances']), 0, "Wrong number of 'standalone' instances.")

			# Now make that version current, and check the quantity of instances again.
			self.execute(
				[
					'version-setcurrent',
					version_one_id
				]
			)

			job_id = self.data['job_id']
			self.follow_job(job_id, timeout=10)
			self.assertTrue(self.success, "Version start job did not succeed.")

			# From that version, query out the instances.
			self.execute(
				[
					'version-instances',
					version_one_id
				]
			)

			# Now there should be one of each.
			self.assertEquals(len(self.data['instances']['web']['instances']), 1, "Wrong number of 'web' instances.")
			self.assertEquals(len(self.data['instances']['standalone']['instances']), 1, "Wrong number of 'standalone' instances.")
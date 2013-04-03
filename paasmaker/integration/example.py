#
# Paasmaker - Platform as a Service
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#

import paasmaker

class ExampleIntegrationTest(paasmaker.common.testhelpers.BaseMultipaasTest):

	def test_simple(self):
		self.add_multipaas_node(pacemaker=True, heart=False, router=False)
		self.add_multipaas_node(pacemaker=False, heart=True, router=False)
		self.add_multipaas_node(pacemaker=False, heart=False, router=True)
		self.start_multipaas()

		with paasmaker.common.testhelpers.MultipaasTestHandler(self):
			#self.assertTrue(False, "Test error.")
			self.assertTrue(True, "Success")
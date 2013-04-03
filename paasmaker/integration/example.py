
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
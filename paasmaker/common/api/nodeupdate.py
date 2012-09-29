
import noderegister

class NodeUpdateAPIRequest(noderegister.NodeRegisterAPIRequest):
	def build_payload(self):
		payload = super(NodeUpdateAPIRequest, self).build_payload()
		payload['uuid'] = self.configuration.get_node_uuid()
		return payload

	def get_endpoint(self):
		return '/node/update'

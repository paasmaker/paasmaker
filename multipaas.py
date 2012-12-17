#!/usr/bin/env python

import json

import paasmaker

multipaas = paasmaker.util.multipaas.MultiPaas()

multipaas.add_node(pacemaker=True, heart=False, router=True)
multipaas.add_node(pacemaker=False, heart=True, router=True)

multipaas.start_nodes()

summary = multipaas.get_summary()

#print json.dumps(summary, indent=4, sort_keys=True)

# Set up initial state.
user_result = multipaas.run_command(['user-create', 'multipaas', 'multipaas@paasmaker.com', 'Multi Paas', 'multipaas'])
role_result = multipaas.run_command(['role-create', 'Administrator', 'ALL'])
workspace_result = multipaas.run_command(['workspace-create', 'Test', 'test', '{}'])

#print json.dumps(user_result, indent=4, sort_keys=True)
#print json.dumps(role_result, indent=4, sort_keys=True)
#print json.dumps(workspace_result, indent=4, sort_keys=True)

multipaas.run_command(['role-allocate', role_result['role']['id'], user_result['user']['id']])

print "Connect to the multipaas on: "
print "http://localhost:%d/" % summary['configuration']['master_port']
print "Routers:"
for node in summary['nodes']:
	if node.has_key('nginx_port'):
		print "Port %d" % node['nginx_port']

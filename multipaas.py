#!/usr/bin/env python

#
# Paasmaker - Platform as a Service
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#

import json
import logging
import uuid
import sys
import time
import os

if not os.path.exists("thirdparty/python/bin/pip"):
	print "virtualenv not installed. Run install.py to set up this directory properly."
	sys.exit(1)

# Activate the environment now, inside this script.
bootstrap_script = "thirdparty/python/bin/activate_this.py"
execfile(bootstrap_script, dict(__file__=bootstrap_script))


import paasmaker

from paasmaker.thirdparty.safeclose import safeclose

# Logging setup.
logging.basicConfig(format='%(asctime)s %(levelname)s %(message)s', level=logging.INFO, stream=sys.stderr)

multipaas = paasmaker.util.multipaas.MultiPaas()

USERNAME = 'multipaas'
PASSWORD = str(uuid.uuid4())[0:8]

def on_exit_request():
	# Clean up.
	multipaas.stop_nodes()
	multipaas.destroy()

	# TODO: Cleanup orphan redis instances and nginx instances.

try:
	with safeclose.section(on_exit_request):
		# Add our nodes.
		multipaas.add_node(pacemaker=True, heart=False, router=True)
		multipaas.add_node(pacemaker=False, heart=True, router=True)

		logging.info("Cluster root: %s", multipaas.cluster_root)

		# Start it up.
		multipaas.start_nodes()

		time.sleep(0.5)

		summary = multipaas.get_summary()

		#print json.dumps(summary, indent=4, sort_keys=True)

		executor = multipaas.get_executor()

		# Set up initial state.
		user_result = executor.run(['user-create', USERNAME, 'multipaas@paasmaker.com', 'Multi Paas', PASSWORD])
		role_result = executor.run(['role-create', 'Administrator', 'ALL'])
		workspace_result = executor.run(['workspace-create', 'Test', 'test', '{}'])

		#print json.dumps(user_result, indent=4, sort_keys=True)
		#print json.dumps(role_result, indent=4, sort_keys=True)
		#print json.dumps(workspace_result, indent=4, sort_keys=True)

		executor.run(['role-allocate', role_result['role']['id'], user_result['user']['id']])

		print "Connect to the multipaas on:"
		print "http://localhost:%d/" % summary['configuration']['master_port']
		print "Using username and password: %s / %s" % (USERNAME, PASSWORD)
		print "Routers:"
		for node in summary['nodes']:
			if node.has_key('nginx_port'):
				print "Port %d" % node['nginx_port']

		close = raw_input("Press enter to close and destroy your cluster.")

		on_exit_request()
except Exception, ex:
	logging.error("Programming error in the MultiPaas.")
	logging.error("Exception:", exc_info=ex)

	multipaas.stop_nodes()
	multipaas.destroy()
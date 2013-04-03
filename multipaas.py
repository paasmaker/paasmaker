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
import tornado.ioloop

# Logging setup.
logging.basicConfig(format='%(asctime)s %(levelname)s %(message)s', level=logging.INFO, stream=sys.stderr)

multipaas = paasmaker.util.multipaas.MultiPaas()

USERNAME = 'multipaas'
PASSWORD = str(uuid.uuid4())[0:8]

def on_exit_request():
	# Clean up.
	multipaas.stop_nodes()
	multipaas.destroy()

	tornado.ioloop.IOLoop.instance().stop()
	sys.exit(0)

def on_ioloop_started():
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

			executor = multipaas.get_executor(tornado.ioloop.IOLoop.instance())

			role_result = {}
			user_result = {}

			def check_success(success, errors):
				if not success:
					print "FAILED TO SET UP MULTIPAAS"
					print errors
					on_exit_request()

			def all_created(success, data, errors):
				check_success(success, errors)
				print "Connect to the multipaas on:"
				print "http://localhost:%d/" % summary['configuration']['master_port']
				print "Using username and password: %s / %s" % (USERNAME, PASSWORD)
				print "Routers:"
				for node in summary['nodes']:
					if node.has_key('nginx_port'):
						print "Port %d" % node['nginx_port']

				close = raw_input("Press enter to close and destroy your cluster.")

				on_exit_request()

			def allocate_role(success, data, errors):
				check_success(success, errors)
				executor.run(
					[
						'role-allocate',
						role_result['role']['id'],
						user_result['user']['id']
					],
					all_created,
				)

			def create_workspace(success, data, errors):
				check_success(success, errors)
				user_result.update(data)
				executor.run(
					[
						'workspace-create',
						'Test',
						'test',
						'{}'
					],
					allocate_role
				)

			def create_user(success, data, errors):
				check_success(success, errors)
				role_result.update(data)
				executor.run(
					[
						'user-create',
						USERNAME,
						'multipaas@paasmaker.com',
						'Multi Paas',
						PASSWORD
					],
					create_workspace
				)

			executor.run(
				[
					'role-create',
					'Administrator',
					'ALL'
				],
				create_user
			)

	except Exception, ex:
		logging.error("Programming error in the MultiPaas.")
		logging.error("Exception:", exc_info=ex)

		multipaas.stop_nodes()
		multipaas.destroy()

tornado.ioloop.IOLoop.instance().add_callback(on_ioloop_started)
tornado.ioloop.IOLoop.instance().start()
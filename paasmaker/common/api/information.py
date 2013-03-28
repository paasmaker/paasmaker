#
# Paasmaker - Platform as a Service
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#

import paasmaker

from apirequest import APIRequest, APIResponse

class InformationAPIRequest(APIRequest):
	"""
	Fetch basic information on a node. Designed for use internally
	to make sure the node can be contacted.
	"""

	def get_endpoint(self):
		return '/information?bypass_ssl=true'
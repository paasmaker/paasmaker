#!/bin/bash

#
# Paasmaker - Platform as a Service
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#

# Activate the virtualenv.
. thirdparty/python/bin/activate

# Build the HTML docs.
make -C documentation/ html

# Deactivate
deactivate
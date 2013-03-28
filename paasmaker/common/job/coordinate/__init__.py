#
# Paasmaker - Platform as a Service
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#

from selectlocations import SelectLocationsJob
from register import RegisterRootJob, RegisterRequestJob
from storeport import StorePortJob
from startup import StartupRootJob, StartupRequestJob
from shutdown import ShutdownRootJob, ShutdownRequestJob
from deregister import DeRegisterRootJob, DeRegisterRequestJob
from current import CurrentVersionRequestJob
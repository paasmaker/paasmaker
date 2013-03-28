#
# Paasmaker - Platform as a Service
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#

from parameters import ParametersService
from filesystem import FilesystemService
from mysql import MySQLService
from postgres import PostgresService
from managedredis import ManagedRedisService
from managedpostgres import ManagedPostgresService
from managedmongodb import ManagedMongoService
from managedmysql import ManagedMySQLService
from s3bucket import S3BucketService
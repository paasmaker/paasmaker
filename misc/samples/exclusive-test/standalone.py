#!/usr/bin/env python

import time
import datetime
import os
import sys

print "Starting standalone instance."

while True:
	time.sleep(2)
	print datetime.datetime.utcnow().isoformat()
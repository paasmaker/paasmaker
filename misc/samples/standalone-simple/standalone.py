
import time
import datetime

print "Starting standalone instance."

while True:
	time.sleep(2)
	print datetime.datetime.utcnow().isoformat()
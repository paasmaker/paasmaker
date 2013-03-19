#!/usr/bin/env python
import os
import glob
import json

def format_environment_variable(variable_name):
	contents = None
	if variable_name in os.environ:
		contents = json.loads(os.environ[variable_name])

	response = 'Contents of %s:\n' % variable_name
	if contents is not None:
		response += json.dumps(contents, indent=4, sort_keys=True)
	else:
		response += '- No contents, variable not set.'

	return response

print 'My working directory: %s' % os.getcwd()
print 'Files in my working directory:'
for filename in glob.glob('*'):
	print '* %s' % filename
print format_environment_variable('PM_SERVICES')
print format_environment_variable('PM_METADATA')
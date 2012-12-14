
import hashlib
import json
import time
import os
import uuid
import logging
import datetime

import paasmaker
from paasmaker.common.controller import BaseController, BaseControllerTest
from paasmaker.common.core import constants
from paasmaker.thirdparty.cronex import cronex
from paasmaker.util.plugin import MODE

import tornado
import colander
from sqlalchemy import func

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

class CronList(object):
	def __init__(self, configuration):
		self.configuration = configuration

	def _max_dates(self, *args):
		dates = []
		for arg in args:
			if arg:
				dates.append(arg.isoformat())

		if len(dates) == 0:
			return "0"
		else:
			return max(*dates)

	def _get_cache_key(self, session):
		updated_cron = session.query(
			func.max(paasmaker.model.ApplicationInstanceTypeCron.updated)
		).scalar()
		deleted_cron = session.query(
			func.max(paasmaker.model.ApplicationInstanceTypeCron.deleted)
		).scalar()
		updated_version = session.query(
			func.max(paasmaker.model.ApplicationVersion.updated)
		).scalar()
		deleted_version = session.query(
			func.max(paasmaker.model.ApplicationVersion.deleted)
		).scalar()

		max_date = self._max_dates(
			updated_cron,
			deleted_cron,
			updated_version,
			deleted_version
		)

		summer = hashlib.md5()
		summer.update(max_date)
		key = summer.hexdigest()

		return key

	def _build_cache(self, session):
		# Filter to only instance types whose versions are current.
		current_version_ids = session.query(
			paasmaker.model.ApplicationVersion.id
		).filter(
			paasmaker.model.ApplicationVersion.is_current == True,
			paasmaker.model.ApplicationVersion.deleted == None
		)
		instance_type_ids = session.query(
			paasmaker.model.ApplicationInstanceType.id
		).filter(
			paasmaker.model.ApplicationInstanceType.application_version_id.in_(current_version_ids)
		)
		tasks = session.query(
			paasmaker.model.ApplicationInstanceTypeCron
		).filter(
			paasmaker.model.ApplicationInstanceTypeCron.application_instance_type_id.in_(instance_type_ids)
		)

		task_buckets = {}
		for task in tasks:
			if not task_buckets.has_key(task.runspec):
				task_buckets[task.runspec] = []

			task_buckets[task.runspec].append(task.id)

		return task_buckets

	def _load_or_build_table(self):
		cachepath = self.configuration.get_scratch_path('crontable')
		session = self.configuration.get_database_session()
		key = self._get_cache_key(session)
		table = None
		if os.path.exists(cachepath):
			# Load it and check the time.
			try:
				parsed = json.loads(open(cachepath, 'r').read())

				if parsed['key'] == key:
					# It's valid.
					table = parsed['table']
			except ValueError, ex:
				# Invalid JSON. Rebuild.
				pass

		if not table:
			# Need to build the table.
			table = self._build_cache(session)

			# Store the table for later.
			open(cachepath, 'w').write(
				json.dumps(
					{
						'key': key,
						'table': table
					}
				)
			)

		return table

	def get_now_tasks(self):
		table = self._load_or_build_table()

		evaluation_time = time.gmtime(time.time())[:5]

		now_tasks = []

		for spec, task_list in table.iteritems():
			for task_id in task_list:
				checker = cronex.CronExpression("%s %d" % (str(spec), task_id))

				if checker.check_trigger(evaluation_time):
					now_tasks.append(task_id)

		return now_tasks

class CronRunJobSchema(colander.MappingSchema):
	task_id = colander.SchemaNode(colander.Integer())

class CronRunJob(paasmaker.common.job.base.BaseJob):
	PARAMETERS_SCHEMA = {MODE.JOB: CronRunJobSchema()}

	def start_job(self, context):
		task_id = self.parameters['task_id']

		session = self.configuration.get_database_session()
		task = session.query(
			paasmaker.model.ApplicationInstanceTypeCron
		).get(task_id)

		self.logger.info("Starting cron task %s" % task.uri)
		self.started = datetime.datetime.now()

		# Find an instance to service us.
		self.logger.info("Looking for instance to service this request.")
		candidates = session.query(
			paasmaker.model.ApplicationInstance
		).filter(
			paasmaker.model.ApplicationInstance.application_instance_type == task.application_instance_type,
			paasmaker.model.ApplicationInstance.state == constants.INSTANCE.RUNNING
		)

		if candidates.count() == 0:
			error_message = "Can't find any running instances to service this request."
			self.logger.error(error_message)
			self.failed(error_message)
			return

		# Pick the first one. That will do.
		# TODO: Use a little bit more intelligence to find an appropriate node.
		instance = candidates[0]

		self.logger.info("Chosen %s (on node %s) to service this request.", instance.instance_id, instance.node.name)

		# Build our HTTP request object.
		kwargs = {}
		kwargs['request_timeout'] = 300 # TODO: This gives it max 5 mins to complete. Check to see if we can make this unlimited.
		kwargs['streaming_callback'] = self._on_data_block
		if task.username:
			self.logger.info("Using supplied username and password.")
			kwargs['auth_username'] = task.username
			kwargs['auth_password'] = task.password

		endpoint = "http://%s:%d%s" % (instance.node.route, instance.port, task.uri)
		self.logger.debug("Resolved endpoint: %s", endpoint)

		request = tornado.httpclient.HTTPRequest(
			endpoint,
			**kwargs
		)
		client = tornado.httpclient.AsyncHTTPClient(io_loop=self.configuration.io_loop)
		self.log_fp = self.logger.takeover_file()
		client.fetch(request, self._on_request_complete)

	def _on_data_block(self, data):
		# Write the data block to the file.
		self.log_fp.write(data)

	def _on_request_complete(self, response):
		self.log_fp.write("\n")
		self.logger.untakeover_file(self.log_fp)
		ended = datetime.datetime.now()
		runtime = (ended - self.started).total_seconds()
		self.logger.info("Runtime: %f seconds.", runtime)
		# See what happened.
		if response.error:
			self.logger.error("Failed to make request:", exc_info=response.error)
			self.failed(str(response.error))
		else:
			self.logger.info("Completed successfully.")
			self.success({}, "Completed successfully.")

	@staticmethod
	def schedule_tasks(configuration, callback):
		new_job_set = []

		session = configuration.get_database_session()

		# Get a list of the tasks.
		lister = CronList(configuration)
		ready_to_run = lister.get_now_tasks()

		def add_job():
			try:
				task_id = ready_to_run.pop()
				task = session.query(
					paasmaker.model.ApplicationInstanceTypeCron
				).get(task_id)

				instance_type = task.application_instance_type

				task_title = "Cron task '%s' for application %s, version %d, at %s" % (
					task.uri,
					task.application_instance_type.application_version.application.name,
					task.application_instance_type.application_version.version,
					datetime.datetime.utcnow().isoformat()
				)

				tags = []
				tags.append('workspace:%d' % instance_type.application_version.application.workspace.id)
				tags.append('workspace:cron:%d' % instance_type.application_version.application.workspace.id)
				tags.append('application:%d' % instance_type.application_version.application.id)
				tags.append('application:cron:%d' % instance_type.application_version.application.id)
				tags.append('application_version:%d' % instance_type.application_version.id)
				tags.append('application_version:cron:%d' % instance_type.application_version.id)
				tags.append('application_instance_type:%d' % instance_type.id)
				tags.append('application_instance_type:cron:%d' % instance_type.id)
				tags.append('application_instance_type_cron:%d' % task.id)

				def on_job_executable():
					# Move onto the next job.
					add_job()

				def on_job_added(new_job_id):
					# Move onto the next job.
					new_job_set.append(new_job_id)
					# Make it executable immediately.
					configuration.job_manager.allow_execution(new_job_id, callback=on_job_executable)

				configuration.job_manager.add_job(
					'paasmaker.job.cron',
					{
						'task_id': task.id
					},
					task_title,
					on_job_added,
					tags=tags
				)

			except IndexError, ex:
				# Got the last job. We're done.
				callback(new_job_set)

			# end of add_job()

		# Kick off the process.
		add_job()

class CronPeriodicManager(object):
	def __init__(self, configuration):
		self.configuration = configuration
		# Create the periodic handler.
		self.periodic = tornado.ioloop.PeriodicCallback(
			self.schedule_jobs,
			60000, # Always every 60 seconds.
			io_loop=configuration.io_loop
		)

		# Figure out how long until the top of the next minute,
		# and then schedule us to start running then.
		now = time.time()
		next_minute_top = (now + 60) - (now % 60)
		configuration.io_loop.add_timeout(next_minute_top, self.start)

		logger.info("Starting to process cron jobs in %d seconds.", next_minute_top - now)

	def start(self):
		logger.info("Starting processing of cron jobs every 60 seconds.")
		self.periodic.start()
		# And do a first run.
		self.schedule_jobs()

	def schedule_jobs(self):
		# Fire off the jobs.
		logger.info("Evaluating cron jobs.")
		CronRunJob.schedule_tasks(self.configuration, self._on_complete)

	def _on_complete(self, tasklist):
		logger.info("Kicked off %d cron jobs.", len(tasklist))

class CronTestController(BaseController):
	AUTH_METHODS = [BaseController.ANONYMOUS]

	def get(self, mode):
		if mode == 'normal':
			self.write("Normal mode.")
			self.finish()
		else:
			# Check user auth.
			# TODO: Actually check this...
			self.write("Password mode " + str(self.request.headers))
			self.finish()

	@staticmethod
	def get_routes(configuration):
		routes = []
		routes.append((r"/cron/test/(\w+)", CronTestController, configuration))
		return routes

class CronRunnerTest(BaseControllerTest):
	config_modules = ['pacemaker', 'heart']

	def setUp(self):
		super(CronRunnerTest, self).setUp()

		self.manager = self.configuration.job_manager

		# Wait for it to start up.
		self.manager.prepare(self.stop, self.stop)
		self.wait()

	def get_app(self):
		self.late_init_configuration(self.io_loop)
		routes = CronTestController.get_routes({'configuration': self.configuration})
		application = tornado.web.Application(routes, **self.configuration.get_tornado_configuration())
		return application

	def get_state(self, job_id):
		self.manager.get_job_state(job_id, self.stop)
		return self.wait()

	def test_cron(self):
		session = self.configuration.get_database_session()

		# Make us a node.
		nodeuuid = str(uuid.uuid4())
		node = paasmaker.model.Node('test', 'localhost', self.get_http_port(), nodeuuid, constants.NODE.ACTIVE)
		nodeuuid = str(uuid.uuid4())
		self.configuration.set_node_uuid(nodeuuid)
		session.add(node)

		# Create the test environment.
		workspace = paasmaker.model.Workspace()
		workspace.name = 'Test'
		workspace.stub = 'test'

		application = paasmaker.model.Application()
		application.workspace = workspace
		application.name = 'foo.com'

		application_version = paasmaker.model.ApplicationVersion()
		application_version.application = application
		application_version.version = 1
		application_version.is_current = True
		application_version.manifest = ''
		application_version.source_path = "paasmaker://foo/bar"
		application_version.source_checksum = 'dummychecksumhere'
		application_version.state = paasmaker.common.core.constants.VERSION.PREPARED

		version_1 = application_version

		instance_type = paasmaker.model.ApplicationInstanceType()
		instance_type.application_version = application_version
		instance_type.name = 'web'
		instance_type.quantity = 1
		instance_type.runtime_name = 'paasmaker.runtime.shell'
		instance_type.runtime_parameters = {}
		instance_type.runtime_version = '1'
		instance_type.startup = {}
		instance_type.placement_provider = 'paasmaker.placement.default'
		instance_type.placement_parameters = {}
		instance_type.exclusive = False
		instance_type.standalone = False

		cron_task = paasmaker.model.ApplicationInstanceTypeCron()
		cron_task.application_instance_type = instance_type
		cron_task.runspec = '* * * * *'
		cron_task.uri = '/cron/test/normal'

		instance = paasmaker.model.ApplicationInstance()
		instance.instance_id = str(uuid.uuid4())
		instance.application_instance_type = instance_type
		instance.node = node
		instance.port = self.get_http_port()
		instance.state = constants.INSTANCE.RUNNING

		instance_type.crons.append(cron_task)
		cron_task_1 = cron_task

		session.add(instance)
		session.add(instance_type)

		application_version = paasmaker.model.ApplicationVersion()
		application_version.application = application
		application_version.version = 2
		application_version.is_current = False
		application_version.manifest = ''
		application_version.source_path = "paasmaker://foo/bar"
		application_version.source_checksum = 'dummychecksumhere'
		application_version.state = paasmaker.common.core.constants.VERSION.PREPARED

		version_2 = application_version

		instance_type = paasmaker.model.ApplicationInstanceType()
		instance_type.application_version = application_version
		instance_type.name = 'web'
		instance_type.quantity = 1
		instance_type.runtime_name = 'paasmaker.runtime.shell'
		instance_type.runtime_parameters = {}
		instance_type.runtime_version = '1'
		instance_type.startup = {}
		instance_type.placement_provider = 'paasmaker.placement.default'
		instance_type.placement_parameters = {}
		instance_type.exclusive = False
		instance_type.standalone = False

		instance = paasmaker.model.ApplicationInstance()
		instance.instance_id = str(uuid.uuid4())
		instance.application_instance_type = instance_type
		instance.node = node
		instance.port = self.get_http_port()
		instance.state = constants.INSTANCE.RUNNING

		cron_task = paasmaker.model.ApplicationInstanceTypeCron()
		cron_task.application_instance_type = instance_type
		cron_task.runspec = '* * * * *'
		cron_task.uri = '/cron/test/protected'
		cron_task.username = 'test'
		cron_task.password = 'test'

		instance_type.crons.append(cron_task)
		cron_task_2 = cron_task

		session.add(instance_type)
		session.add(instance)
		session.commit()
		session.refresh(cron_task_1)
		session.refresh(cron_task_2)
		session.refresh(version_1)
		session.refresh(version_2)

		# Now get a list of the tasks.
		lister = CronList(self.configuration)
		ready_to_run = lister.get_now_tasks()

		self.assertEquals(1, len(ready_to_run), "Incorrect number of ready to run tasks.")
		self.assertEquals(ready_to_run[0], cron_task_1.id, "Wrong task ready to run.")

		# Do the cron list again. It should fetch from cache.
		lister = CronList(self.configuration)
		ready_to_run = lister.get_now_tasks()

		self.assertEquals(1, len(ready_to_run), "Incorrect number of ready to run tasks.")
		self.assertEquals(ready_to_run[0], cron_task_1.id, "Wrong task ready to run.")

		# Make the second version the current version.
		version_2.make_current(session)

		# Do the cron list again. The cache should be invalid, and it should return a different
		# result.
		lister = CronList(self.configuration)
		ready_to_run = lister.get_now_tasks()

		self.assertEquals(1, len(ready_to_run), "Incorrect number of ready to run tasks.")
		self.assertEquals(ready_to_run[0], cron_task_2.id, "Wrong task ready to run.")

		# Schedule and run those jobs.
		CronRunJob.schedule_tasks(self.configuration, self.stop)
		tasks = self.wait()

		self.assertEquals(1, len(tasks), "Too many tasks scheduled.")

		task_id = tasks[0]

		self.short_wait_hack()

		self.manager.get_pretty_tree(task_id, self.stop)
		tree = self.wait()
		#print json.dumps(tree, indent=4, sort_keys=True)

		state = self.get_state(task_id)

		self.assertEquals(state, constants.JOB.SUCCESS, "Should have succeeded.")

		# Make the first version the current version.
		version_1.make_current(session)

		# And try again.
		CronRunJob.schedule_tasks(self.configuration, self.stop)
		tasks = self.wait()

		self.assertEquals(1, len(tasks), "Too many tasks scheduled.")

		task_id = tasks[0]

		self.short_wait_hack()

		self.manager.get_pretty_tree(task_id, self.stop)
		tree = self.wait()
		#print json.dumps(tree, indent=4, sort_keys=True)

		state = self.get_state(task_id)

		self.assertEquals(state, constants.JOB.SUCCESS, "Should have succeeded.")
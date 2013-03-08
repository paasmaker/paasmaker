#!/usr/bin/env python

# Python imports.
import os
import sys
import platform

# TODO: What happens to this virtualenv activation when Torndao's
# autoreload kicks in?

# Check our current directory. Many things expect to be in the path
# of the server file, so switch directory if we need to.
paasmaker_home = os.path.dirname(os.path.abspath(__file__))
if paasmaker_home != os.getcwd():
	# Make the current directory the one where the script is.
	os.chdir(paasmaker_home)

if not os.path.exists("thirdparty/python/bin/pip"):
	print "virtualenv not installed. Run install.py to set up this directory properly."
	sys.exit(1)

# Activate the environment now, inside this script.
bootstrap_script = "thirdparty/python/bin/activate_this.py"
execfile(bootstrap_script, dict(__file__=bootstrap_script))

# Continue with normal startup.

# External library imports.
import tornado.ioloop
import tornado.web
from tornado.options import options
from pubsub import pub
from pubsub.utils.exchandling import IExcHandler
from paasmaker.thirdparty.safeclose import safeclose
import tornadio2

# Internal imports.
import paasmaker

# Logging setup.
import logging
logging.basicConfig(format='%(asctime)s %(levelname)s %(message)s', level=logging.INFO)

# Setup pubsub exception handling.
# TODO: Figure out what to really do with this...
# But this at least prevents it from aborting other things.
class PaasmakerPubSubExceptionHandler(IExcHandler):
	def __call__(self, listenerID, topicObj):
		logging.error("Exception in pub/sub handler:", exc_info=True)
		logging.error("Listener ID: %s", listenerID)

pub.setListenerExcHandler(PaasmakerPubSubExceptionHandler())

# Parse command line options.
options.parse_command_line()

# Load configuration
logging.info("Loading configuration...")
configuration = paasmaker.common.configuration.Configuration()
configuration.load_from_file(['paasmaker.yml', '/etc/paasmaker/paasmaker.yml'])

# Reset the log level.
logging.info("Resetting server log level to %s.", configuration['server_log_level'])
logger = logging.getLogger()
logger.setLevel(getattr(logging, configuration['server_log_level']))
configuration.dump()

# Does the PID file already exist? If so, we're probably already running.
is_debug = (options.debug == 1)
pid_path = configuration.get_flat('pid_path')
if os.path.exists(pid_path):
	# Check the process.
	pid = int(open(pid_path, 'r').read())
	is_running = paasmaker.util.processcheck.ProcessCheck.is_running(pid, 'pm-server')
	# If we're in debug mode, Tornado will auto reload on file changes,
	# which causes this to think it's already running and exit.
	if is_running and not is_debug:
		logger.critical("Found existing process at pid %s, not starting again.", pid)
		sys.exit(1)

# Initialise the system.
logging.info("Initialising system.")
route_extras = dict(configuration=configuration)
routes = []

# Set up the job logger.
paasmaker.util.joblogging.JobLoggerAdapter.setup_joblogger(configuration)
configuration.setup_job_watcher()

# Set up the node logging. This may not set up the node logging
# if this node has never been registered; but we call it again
# later to handle that case.
configuration.setup_node_logging()

# Add any routes defined by plugins first. This makes them override internal routes.
routes_plugins = configuration.plugins.plugins_for(
	paasmaker.util.plugin.MODE.STARTUP_ROUTES
)
for plugin in routes_plugins:
	instance = configuration.plugins.instantiate(
		plugin,
		paasmaker.util.plugin.MODE.STARTUP_ROUTES
	)
	instance.add_routes(
		routes,
		route_extras
	)

if configuration.is_pacemaker():
	# Pacemaker setup.
	# Connect to the database.
	logging.info("Database connection and table creation...")
	logging.info("Please be patient, this can take a few moments on first run.")
	configuration.setup_database()

	logging.info("Setting up pacemaker routes...")
	routes.extend(paasmaker.pacemaker.controller.index.IndexController.get_routes(route_extras))
	routes.extend(paasmaker.pacemaker.controller.overview.OverviewController.get_routes(route_extras))
	routes.extend(paasmaker.pacemaker.controller.login.LoginController.get_routes(route_extras))
	routes.extend(paasmaker.pacemaker.controller.login.LogoutController.get_routes(route_extras))
	routes.extend(paasmaker.pacemaker.controller.user.UserEditController.get_routes(route_extras))
	routes.extend(paasmaker.pacemaker.controller.user.UserListController.get_routes(route_extras))
	routes.extend(paasmaker.pacemaker.controller.profile.ProfileController.get_routes(route_extras))
	routes.extend(paasmaker.pacemaker.controller.profile.ProfileUserdataController.get_routes(route_extras))
	routes.extend(paasmaker.pacemaker.controller.profile.ProfileResetAPIKeyController.get_routes(route_extras))
	routes.extend(paasmaker.pacemaker.controller.workspace.WorkspaceEditController.get_routes(route_extras))
	routes.extend(paasmaker.pacemaker.controller.workspace.WorkspaceListController.get_routes(route_extras))

	routes.extend(paasmaker.pacemaker.controller.tools.ToolsController.get_routes(route_extras))

	routes.extend(paasmaker.pacemaker.controller.role.RoleEditController.get_routes(route_extras))
	routes.extend(paasmaker.pacemaker.controller.role.RoleListController.get_routes(route_extras))
	routes.extend(paasmaker.pacemaker.controller.role.RoleAllocationListController.get_routes(route_extras))
	routes.extend(paasmaker.pacemaker.controller.role.RoleAllocationAssignController.get_routes(route_extras))
	routes.extend(paasmaker.pacemaker.controller.role.RoleAllocationUnAssignController.get_routes(route_extras))

	routes.extend(paasmaker.pacemaker.controller.application.ApplicationListController.get_routes(route_extras))
	routes.extend(paasmaker.pacemaker.controller.application.ApplicationNewController.get_routes(route_extras))
	routes.extend(paasmaker.pacemaker.controller.application.ApplicationController.get_routes(route_extras))
	routes.extend(paasmaker.pacemaker.controller.application.ApplicationSetCurrentController.get_routes(route_extras))
	routes.extend(paasmaker.pacemaker.controller.application.ApplicationDeleteController.get_routes(route_extras))
	routes.extend(paasmaker.pacemaker.controller.application.ApplicationServiceListController.get_routes(route_extras))
	routes.extend(paasmaker.pacemaker.controller.scmlist.ScmListController.get_routes(route_extras))

	routes.extend(paasmaker.pacemaker.controller.configuration.ConfigurationDumpController.get_routes(route_extras))
	routes.extend(paasmaker.pacemaker.controller.configuration.PluginInformationController.get_routes(route_extras))

	routes.extend(paasmaker.pacemaker.controller.job.JobListController.get_routes(route_extras))
	routes.extend(paasmaker.pacemaker.controller.job.JobAbortController.get_routes(route_extras))

	routes.extend(paasmaker.pacemaker.controller.router.TableDumpController.get_routes(route_extras))

	routes.extend(paasmaker.pacemaker.controller.version.VersionController.get_routes(route_extras))
	routes.extend(paasmaker.pacemaker.controller.version.VersionInstancesController.get_routes(route_extras))
	routes.extend(paasmaker.pacemaker.controller.version.VersionRegisterController.get_routes(route_extras))
	routes.extend(paasmaker.pacemaker.controller.version.VersionStartupController.get_routes(route_extras))
	routes.extend(paasmaker.pacemaker.controller.version.VersionShutdownController.get_routes(route_extras))
	routes.extend(paasmaker.pacemaker.controller.version.VersionDeRegisterController.get_routes(route_extras))
	routes.extend(paasmaker.pacemaker.controller.version.VersionDeleteController.get_routes(route_extras))

	routes.extend(paasmaker.pacemaker.controller.node.NodeRegisterController.get_routes(route_extras))
	routes.extend(paasmaker.pacemaker.controller.node.NodeListController.get_routes(route_extras))
	routes.extend(paasmaker.pacemaker.controller.node.NodeDetailController.get_routes(route_extras))
	routes.extend(paasmaker.pacemaker.controller.package.PackageSizeController.get_routes(route_extras))
	routes.extend(paasmaker.pacemaker.controller.package.PackageDownloadController.get_routes(route_extras))

	if configuration.get_flat('pacemaker.allow_uploads'):
		routes.extend(paasmaker.pacemaker.controller.upload.UploadController.get_routes(route_extras))

if configuration.is_heart():
	# Heart setup.
	routes.extend(paasmaker.heart.controller.instance.InstanceExitController.get_routes(route_extras))

if configuration.is_router():
	# Router setup.
	# Connect to redis.
	pass

logging.info("Setting up common routes...")
routes.extend(paasmaker.common.controller.information.InformationController.get_routes(route_extras))

# The socketio routers. It's all in a single controller for the moment.
socketio_router = tornadio2.TornadioRouter(
	paasmaker.pacemaker.controller.stream.StreamConnection
)
# Hack to store the configuration on the socket.io router.
socketio_router.configuration = configuration

# Set up the application object.
# NOTE: What's happening here is that the socket.io router takes
# over routing, and passes through requests to the normal HTTP endpoints.
logging.info("Setting up the application.")
application_settings = configuration.get_tornado_configuration()
# We don't need to have a second socket_io_port, so choose a high port
# that's free for this purpose. Otherwise tornadio2 doesn't work.
tornadio_port_finder = paasmaker.util.port.FreePortFinder()
application_settings['socket_io_port'] = tornadio_port_finder.free_in_range(65000, 65500)
application = tornado.web.Application(
	socketio_router.apply_routes(routes),
	**application_settings
)

@tornado.stack_context.contextlib.contextmanager
def handle_runtime_exception():
	try:
		yield
	except Exception, ex:
		# Log what happened.
		logging.error("Runtime exception:", exc_info=True)

# Some tasks to perform once we're registered with the master for the
# first time this startup.
def on_registered_with_master():
	# Only called the first time we register with the master after startup.
	# These tasks are delayed because new nodes won't have a UUID yet,
	# which these tasks require.

	# Add this pacemaker to the routing table.
	if configuration.is_pacemaker():
		session = configuration.get_database_session()
		def success_insert():
			session.close()
			logger.info("Successfully inserted this pacemaker into the routing table.")
		def failed_insert(message, exception=None):
			session.close()
			logger.error("Failed to place pacemaker into the routing table.")
			logger.error(message)
			if exception:
				lgoger.error("Exception:", exc_info=exception)

		node = session.query(
			paasmaker.model.Node,
		).filter(
			paasmaker.model.Node.uuid == configuration.get_node_uuid()
		).first()

		pacemaker_updater = paasmaker.common.job.routing.routing.RouterTablePacemakerUpdate(
			configuration,
			node,
			True,
			logging
		)
		pacemaker_updater.update(success_insert, failed_insert)

	# Try again to set up node logging, if it did not previously work.
	# This is because this might be the first time we've registered.
	configuration.setup_node_logging()

def on_completed_startup():
	if platform.system() != 'Darwin' and not is_debug:
		# Fork into the background.
		fork_result = os.fork()
		if fork_result != 0:
			# I'm the parent.
			sys.exit(0)

	# Write out our PID file.
	fp = open(pid_path, 'w')
	fp.write(str(os.getpid()))
	fp.close()

	# Start listening for HTTP requests, as everything is ready.
	# Also, use a different context handler - now that the server is running,
	# exceptions thrown should not cause the server to exit.
	with tornado.stack_context.StackContext(handle_runtime_exception):
		logging.info("Listening on port %d", configuration['http_port'])
		application.listen(configuration['http_port'])
		logging.info("All systems are go.")

		# Subscribe for when the node is registered.
		pub.subscribe(on_registered_with_master, 'node.firstregistration')

		# Register the node with the server.
		# This periodic manager will handle keeping it up to date.
		configuration.node_register_periodic = paasmaker.common.api.NodeUpdatePeriodicManager(configuration)

		# Also, start up the periodic router log reader now as well, if configured to do so.
		if configuration.is_router() and configuration.get_flat('router.process_stats'):
			configuration.stats_reader_periodic = paasmaker.router.stats.StatsLogPeriodicManager(configuration)
			configuration.stats_reader_periodic.start()

		# Start up the cron manager.
		if configuration.is_pacemaker() and configuration.get_flat('pacemaker.run_crons'):
			configuration.cron_periodic = paasmaker.pacemaker.cron.cronrunner.CronPeriodicManager(configuration)

		# Set up the health checks.
		if configuration.is_pacemaker() and configuration.get_flat('pacemaker.health.enabled'):
			logger.info("Starting up health manager, because it's configured to run on this node.")
			configuration.startup_health_manager()

		# Set up the periodic tasks.
		configuration.startup_periodic_manager()

def on_intermediary_started(message):
	logger.info(message)
	on_intermediary_started.required -= 1
	# See if everything is ready.
	if on_intermediary_started.required <= 0:
		# Check instances, if we're a heart.
		# We don't do this until the intermediaries are started,
		# as instances may depend on those intermediaries.
		if configuration.is_heart():
			configuration.instances.check_instances_startup(on_check_instances_complete)
		else:
			on_completed_startup()
	else:
		logger.info("Still waiting on %d other things for startup.", on_intermediary_started.required)

on_intermediary_started.required = 0

def on_intermediary_failed(message, exception=None):
	logger.error(message)
	if exception:
		logger.error("Exception:", exc_info=exception)
	logger.critical("Aborting startup due to failure.")
	tornado.ioloop.IOLoop.instance().stop()

def on_check_instances_complete(altered_instances):
	logger.info("%d instances changed state on startup.", len(altered_instances))
	on_completed_startup()

def on_redis_started(redis):
	# Well, we don't care about the redis client passed,
	# but mark this item as complete.
	on_intermediary_started("Started a redis successfully.")

@tornado.stack_context.contextlib.contextmanager
def handle_startup_exception():
	try:
		yield
	except Exception, ex:
		# Log what happened.
		logging.error("A startup task raised an exception.", exc_info=True)
		logging.critical("Aborting startup due to failure.")
		tornado.ioloop.IOLoop.instance().stop()

def on_ioloop_started():
	logger.debug("IO loop running. Launching other connections.")

	# For the job manager startup.
	on_intermediary_started.required += 1
	# For the managed NGINX startup.
	on_intermediary_started.required += 1
	# For the possibly managed router table redis startup.
	on_intermediary_started.required += 1
	# For the possibly managed stats redis startup.
	on_intermediary_started.required += 1

	# Any plugins that want to perform some async startup.
	async_startup_plugins = configuration.plugins.plugins_for(
		paasmaker.util.plugin.MODE.STARTUP_ASYNC_PRELISTEN
	)
	on_intermediary_started.required += len(async_startup_plugins)

	# *********************************************
	# THESE tasks are not in the context manager, because they can fail.
	# If they fail, they catch up later - the job manager has a
	# watchdog to ensure it reconnects, and the other two are on
	# demand, and failure means the appropriate code will retry.

	# Job manager
	logger.info("Starting job manager (async)...")
	configuration.startup_job_manager(on_intermediary_started, on_intermediary_failed)

	# Possibly managed routing table startup.
	logger.info("Starting router table redis (async)...")
	configuration.get_router_table_redis(on_redis_started, on_intermediary_failed)

	# Possibly managed stats redis startup.
	logger.info("Starting stats redis (async)...")
	configuration.get_stats_redis(on_redis_started, on_intermediary_failed)

	with tornado.stack_context.StackContext(handle_startup_exception):
		# Managed NGINX.
		if configuration.get_flat('router.enabled') and configuration.get_flat('router.nginx.managed'):
			logger.info("Starting managed nginx (async)...")
			nginx = paasmaker.router.router.NginxRouter(configuration)
			nginx.startup(on_intermediary_started, on_intermediary_failed)
		else:
			# Call the intermediary to decrement the list of jobs.
			on_intermediary_started("Don't need to start managed NGINX.")

		# Kick off all the async startup plugins.
		for plugin in async_startup_plugins:
			logger.info("Starting async startup plugin %s..." % plugin)
			instance = configuration.plugins.instantiate(
				plugin,
				paasmaker.util.plugin.MODE.STARTUP_ASYNC_PRELISTEN
			)
			instance.startup_async_prelisten(
				on_intermediary_started,
				on_intermediary_failed
			)

		logger.debug("Launched all startup jobs.")

@tornado.stack_context.contextlib.contextmanager
def handle_shutdown_exception_prenotify():
	try:
		yield
	except Exception, ex:
		# Log what happened.
		# But let other things continue to shutdown.
		on_exit_prenotify_complete("A shutdown task raised an exception.", exception=ex)

@tornado.stack_context.contextlib.contextmanager
def handle_shutdown_exception_postnotify():
	try:
		yield
	except Exception, ex:
		# Log what happened.
		# But let other things continue to shutdown.
		on_exit_postnotify_complete("A shutdown task raised an exception.", exception=ex)

def on_exit_request():
	# Did we even register with the master?
	# If not, simply exit now.
	uuid = configuration.get_node_uuid()
	if not uuid:
		logging.info("Never registered with a master node. Moving directly to exit phase.")
		on_actual_exit()
		return

	# Stop the jobs manager watchdog.
	configuration.job_manager.watchdog.disable()

	# Check all instances for shutdown, if we're a heart.
	if hasattr(configuration, 'node_register_periodic'):
		configuration.node_register_periodic.stop()

	if configuration.is_heart():
		configuration.instances.check_instances_shutdown(on_exit_instances_checked)
	else:
		on_exit_instances_checked([])

def on_exit_instances_checked(altered_list):
	logger.info("Finished checking instances.")
	on_exit_plugins_prenotify()

def on_exit_plugins_prenotify():
	# Store the count here.
	on_exit_plugins_prenotify.required = 0

	# Remove this pacemaker from the routing table.
	if configuration.is_pacemaker():
		on_exit_plugins_prenotify.required += 1

	# Figure out what plugins want to run before we notify the master.
	shutdown_plugins = configuration.plugins.plugins_for(
		paasmaker.util.plugin.MODE.SHUTDOWN_PRENOTIFY
	)
	on_exit_plugins_prenotify.required += len(shutdown_plugins)

	logger.info("Launching %d pre-notification shutdown plugins.", len(shutdown_plugins))

	# Launch plugins.
	with tornado.stack_context.StackContext(handle_shutdown_exception_prenotify):
		for plugin in shutdown_plugins:
			instance = configuration.plugins.instantiate(
				plugin,
				paasmaker.util.plugin.MODE.SHUTDOWN_PRENOTIFY
			)
			instance.shutdown_prenotify(
				on_exit_prenotify_complete,
				on_exit_prenotify_complete
			)

	# Remove this pacemaker from the routing table.
	if configuration.is_pacemaker():
		session = configuration.get_database_session()
		def success_remove():
			session.close()
			logger.info("Successfully removed this pacemaker from the routing table.")
			on_exit_prenotify_complete("Pacemaker router table removal.")
		def failed_remove(message, exception=None):
			session.close()
			logger.error("Failed to remove this pacemaker from the routing table.")
			logger.error(message)
			if exception:
				lgoger.error("Exception:", exc_info=exception)
			on_exit_prenotify_complete("Pacemaker router table removal.")

		node = session.query(
			paasmaker.model.Node,
		).filter(
			paasmaker.model.Node.uuid == configuration.get_node_uuid()
		).first()

		if node:
			pacemaker_updater = paasmaker.common.job.routing.routing.RouterTablePacemakerUpdate(
				configuration,
				node,
				False,
				logging
			)
			pacemaker_updater.update(success_remove, failed_remove)
		else:
			# A mismatch where it was unable to find the node.
			# This can be caused by a different on disk UUID to
			# that in the database.
			# Proceed to shutdown.
			on_exit_prenotify_complete("This node has a UUID mismatch. Allowing exit.")
	else:
		# Proceed to shutdown.
		on_exit_prenotify_complete("Not a pacemaker.")

def on_exit_prenotify_complete(message, exception=None):
	on_exit_plugins_prenotify.required -= 1

	if on_exit_plugins_prenotify.required <= 0:
		# We're done. Report the shutdown.
		report_shutdown()
	else:
		logger.info("%d prenotify plugins still waiting to run." % on_exit_plugins_prenotify.required)

def report_shutdown():
	# Report that we're shutting down.
	# This also sends back all the instance statuses.
	# If it fails, we exit anyway. TODO: Is this right?
	logger.debug("Reporting shutdown with master...")
	request = paasmaker.common.api.NodeShutdownAPIRequest(configuration)
	request.send(on_told_master_shutdown)

def on_told_master_shutdown(response):
	if not response.success or len(response.errors) > 0:
		logger.error("Unable to shutdown with the master node.")
		for error in response.errors:
			logger.error(error)
		logger.error("Exiting anyway...")
	else:
		logger.info("Successfully shutdown with master.")

	# Run any shutdown plugins, post notify.
	on_exit_plugins_postnotify()

def on_exit_plugins_postnotify():
	# Store the count here.
	on_exit_plugins_postnotify.required = 0

	# Figure out what plugins want to run after we've notified the master.
	shutdown_plugins = configuration.plugins.plugins_for(
		paasmaker.util.plugin.MODE.SHUTDOWN_POSTNOTIFY
	)
	on_exit_plugins_postnotify.required += len(shutdown_plugins)

	logger.info("Launching %d post-notification shutdown plugins.", len(shutdown_plugins))

	if len(shutdown_plugins) == 0:
		# Continue directly.
		on_exit_postnotify_complete("No post-notification plugins to execute.")
	else:
		with tornado.stack_context.StackContext(handle_shutdown_exception_postnotify):
			for plugin in shutdown_plugins:
				instance = configuration.plugins.instantiate(
					plugin,
					paasmaker.util.plugin.MODE.SHUTDOWN_POSTNOTIFY
				)
				instance.shutdown_postnotify(
					on_exit_postnotify_complete,
					on_exit_postnotify_complete
				)

def on_exit_postnotify_complete(message, exception=None):
	on_exit_plugins_postnotify.required -= 1

	if on_exit_plugins_postnotify.required <= 0:
		# We're done. Really shutdown now.
		on_actual_exit()
	else:
		logger.info("%d postnotify plugins still waiting to run." % on_exit_plugins_postnotify.required)

def on_actual_exit():
	# Now stop any managed daemons.
	nginx = paasmaker.router.router.NginxRouter(configuration)
	nginx.shutdown()

	configuration.shutdown_managed_redis()

	# And really, really exit.
	logging.info("Exiting.")
	if os.path.exists(pid_path):
		os.unlink(pid_path)
	else:
		logging.error("No PID file exists, but exiting anyway.")
	sys.exit(0)

# Commence the application.
if __name__ == "__main__":
	# Add a callback to get started once the IO loop is up and running.
	tornado.ioloop.IOLoop.instance().add_callback(on_ioloop_started)

	# Start up the IO loop.
	with safeclose.section(on_exit_request):
		# This is the socket.io launcher, which routes between
		# socket.io requests and normal HTTP requests. It also
		# starts the IO loop for us.
		tornadio2.SocketServer(application)

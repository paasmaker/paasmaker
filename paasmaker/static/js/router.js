define([
	'jquery',
	'underscore',
	'backbone',
	'tpl!templates/layout/breadcrumb.html',
	'models/node',
	'models/user',
	'models/role',
	'models/application',
	'models/version',
	'models/workspace',
	'models/service',
	'views/node/list',
	'views/workspace/sidebar',
	'views/node/sidebar',
	'views/node/detail',
	'views/administration/sidebar',
	'views/administration/profile',
	'views/administration/list',
	'views/administration/user-list',
	'views/layout/genericloading',
	'views/administration/user-edit',
	'views/administration/role-list',
	'views/administration/role-edit',
	'views/administration/role-allocation-list',
	'views/administration/role-allocation-assign',
	'views/widget/genericjobslist',
	'views/administration/router-dump',
	'views/administration/configuration-dump',
	'views/administration/plugin-dump',
	'views/workspace/list',
	'views/application/list',
	'views/application/detail',
	'views/version/detail',
	'views/widget/genericjob',
	'views/application/new',
	'views/widget/fileupload',
	'views/workspace/edit',
	'views/application/services',
	'views/version/manifest',
	'views/widget/genericlog',
	'views/service/export',
	'views/service/import'
], function($, _, Backbone,
	breadcrumbTemplate,
	NodeModel,
	UserModel,
	RoleModel,
	ApplicationModel,
	VersionModel,
	WorkspaceModel,
	ServiceModel,
	NodeListView,
	WorkspaceSidebarList,
	NodeSidebarList,
	NodeDetailView,
	AdministrationSidebarList,
	ProfileView,
	AdministrationListView,
	UserListView,
	GenericLoadingView,
	UserEditView,
	RoleListView,
	RoleEditView,
	RoleAllocationListView,
	RoleAllocationAssignView,
	GenericJobsListView,
	RouterDumpView,
	ConfigurationDumpView,
	PluginsDumpView,
	WorkspaceListView,
	ApplicationListView,
	ApplicationDetailView,
	VersionDetailView,
	GenericJobView,
	ApplicationNewView,
	FileUploadView, // Not actually used, but referenced here to ensure it ends up in the built version.
	WorkspaceEditView,
	ApplicationServicesView,
	VersionManifestView,
	GenericLogView,
	ServiceExportView,
	ServiceImportView
) {
	var pages = {
		workspaces: $('.page-workspaces'),
		nodes: $('.page-nodes'),
		administration: $('.page-administration'),
		'404': $('.page-404')
	};

	var sidebars = {};

	var AppRouter = Backbone.Router.extend({
		initialize: function() {
			this.route(/^$/, "workspaceList");

			this.route('workspace/list', 'workspaceList');
			this.route(/^workspace\/(\d+)\/applications$/, 'applicationList');
			this.route(/^workspace\/(\d+)$/, 'workspaceEdit');
			this.route('workspace/create', 'workspaceEdit');
			this.route(/^job\/list\/workspace\/(\d+)$/, 'workspaceJobsList');
			this.route(/^job\/list\/workspace\/(\d+)\?sub\=cron$/, 'workspaceJobsList');

			this.route(/^workspace\/(\d+)\/applications\/new$/, 'applicationNew');
			this.route(/^workspace\/(\d+)\/applications\/new\/([-a-z0-9]+)$/, 'applicationNewJob');

			this.route(/^application\/(\d+)$/, 'applicationView');
			this.route(/^application\/(\d+)\/newversion$/, 'applicationNewVersion');
			this.route(/^application\/(\d+)\/newversion\/([-a-z0-9]+)$/, 'applicationNewVersionJob');
			this.route(/^application\/(\d+)\/services$/, 'applicationServices');
			this.route(/^application\/(\d+)\/delete\/([-a-z0-9]+)$/, 'applicationDeleteJob');
			this.route(/^job\/list\/application\/(\d+)$/, 'applicationJobsList');
			this.route(/^job\/list\/application\/(\d+)\?sub\=cron$/, 'applicationJobsList');
			this.route(/^version\/(\d+)$/, 'versionView');
			this.route(/^version\/(\d+)\/log\/([-a-z0-9]+)$/, 'versionLogView');
			this.route(/^version\/(\d+)\/(start|stop|register|deregister|setcurrent|quantity)\/([-a-z0-9]+)$/, 'versionJob');
			this.route(/^version\/(\d+)\/manifest$/, 'versionManifest');
			this.route(/^job\/list\/version\/(\d+)$/, 'versionJobsList');
			this.route(/^job\/list\/version\/(\d+)\?sub\=cron$/, 'versionJobsList');

			this.route(/^service\/export\/(\d+)$/, 'serviceExport');
			this.route(/^service\/import\/(\d+)$/, 'serviceImport');
			this.route(/^service\/import\/(\d+)\/([-a-z0-9]+)$/, 'serviceImportJob');

			this.route('node/list', 'nodeList');
			this.route(/^node\/(\d+)$/, 'nodeDetail');
			this.route(/^node\/(\d+)\/log\/([-a-z0-9]+)$/, 'nodeLogView');

			this.route('administration/list', 'administrationList');
			this.route('profile', 'yourProfile');

			this.route('user/list', 'userList');
			this.route(/^user\/(\d+)$/, 'userEdit');
			this.route('user/create', 'userEdit');

			this.route('role/list', 'roleList');
			this.route(/^role\/(\d+)$/, 'roleEdit');
			this.route('role/create', 'roleEdit');

			this.route('role/allocation/list', 'roleAllocationList');
			this.route('role/allocation/assign', 'roleAllocationAssign');

			this.route('job/list/health', 'adminHealthJobs');
			this.route('job/list/periodic', 'adminPeriodicJobs');

			this.route('router/dump', 'adminRouterDump');
			this.route('configuration/dump', 'adminConfigurationDump');
			this.route('configuration/plugins', 'adminPluginsDump');

			// TODO: Catch the default.
			//this.route('*path', 'defaultAction');
			//this.on('route', this.defaultAction, this);
		},

		/* HELPERS */

		ensureVisible: function(section) {
			// Get the current view to "destroy" itself.
			if (this.currentMainView) {
				this.currentMainView.destroy();
				this.currentMainView = null;
			}

			// Hide all pages.
			var _self = this;
			_.each(pages, function(value, key, list) {
				if(section != key) {
					value.hide();
				}
			});
			// Show the right page.
			_.each(pages, function(value, key, list) {
				if(section == key) {
					_self.currentPage = value;
					if (!value.is(':visible')) {
						value.fadeIn();
					}
				}
			});

			this.createSidebar(section);
		},

		createSidebar: function(section) {
			if(!sidebars[section]) {
				if(section == 'nodes') {
					sidebars[section] = new NodeSidebarList({
						collection: this.context.nodes,
						el: $('.sidebar', this.currentPage)
					});

					// Load the initial set of nodes.
					this.context.nodes.fetch();
				}
				if(section == 'workspaces') {
					sidebars[section] = new WorkspaceSidebarList({
						collection: this.context.workspaces,
						el: $('.sidebar', this.currentPage)
					});
				}
				if(section == 'administration') {
					sidebars[section] = new AdministrationSidebarList({
						collection: this.context.administrations,
						el: $('.sidebar', this.currentPage)
					});
				}
			}
		},

		breadcrumbs: function(crumbs) {
			var container = $('ul.breadcrumb', this.currentPage);
			container.html(breadcrumbTemplate({crumbs: crumbs}));
			var _self = this;
			$('a', container).click(function(e) {
				_self.context.navigate($(e.currentTarget).attr('href'));
				return false;
			});
		},

		adminSetActive: function(override) {
			var path = window.location.pathname;
			if (override) {
				path = override;
			}
			// Mark us as active.
			this.context.administrations.invoke('set', {active: false});
			this.context.administrations.findWhere({path: path}).set({active: true});
		},

		setMainView: function(view) {
			if (this.currentMainView) {
				this.currentMainView.destroy();
			}

			this.currentMainView = view;
		},

		workspaceSetActive: function(active) {
			if (sidebars['workspaces']) {
				sidebars['workspaces'].setActive(active);
			}
		},

		genericJobsListPage: function(sourceUrl, title) {
			this.setMainView(new GenericJobsListView({
				url: sourceUrl,
				title: title,
				el: $('.mainarea', this.currentPage)
			}));
		},

		genericDataTemplatePage: function(url, view) {
			this.setMainView(new view({
				el: $('.mainarea', this.currentPage)
			}));

			// TODO: Handle when you navigate away before this returns.
			$.ajax({
				url: url,
				dataType: 'json',
				success: _.bind(this.currentMainView.dataReady, this.currentMainView),
				error: _.bind(this.currentMainView.loadingError, this.currentMainView)
			});
		},

		fromCollectionOrServer: function(server_id, collection, model, innerFunction, alreadyLoadedCallback) {
			// Fetch the given object from the given collection,
			// or fetch it from the server if we need to.
			// Calls the innerFunction() with the object once it has it.
			// It calls alreadyLoadedCallback() after innerFunction() if the object
			// was loaded without a hit to the server.

			// Try to load the object first.
			var obj = collection.get(server_id);
			if (obj) {
				innerFunction(obj);
				if (alreadyLoadedCallback) {
					alreadyLoadedCallback(obj);
				}
			} else {
				this.setMainView(new GenericLoadingView({el: $('.mainarea', this.currentPage)}));

				this.breadcrumbs([
					{href: '/workspace/list', title: 'Workspaces'},
					{href: '#', title: 'Loading ...'}
				]);

				// Load it directly from the server.
				obj = new model({'id': server_id});
				obj.fetch({
					success: function(model, response, options) {
						// Add to collection, and fetch back, so events work correctly.
						collection.add(model);
						result = collection.get(model.id);
						innerFunction(result);
					},
					error: _.bind(this.currentMainView.loadingError, this.currentMainView)
				});
			}
		},

		/* CONTROLLER FUNCTIONS */

		workspaceEdit: function(workspace_id) {
			this.ensureVisible('workspaces');
			this.workspaceSetActive('workspace-' + workspace_id);

			var _self = this;
			function workspaceEditInner(workspace) {
				var crumbs = [
					{href: '/workspace/list', title: 'Workspaces'}
				];
				if (workspace) {
					crumbs.push({href: '/workspace/' + workspace_id + '/applications', title: workspace.attributes.name});
					crumbs.push({href: '/workspace/' + workspace_id, title: 'Edit'});
				} else {
					_self.workspaceSetActive('create-workspace');
					crumbs.push({href: '/workspace/create', title: 'Create workspace'})
				}
				_self.breadcrumbs(crumbs);

				_self.setMainView(new WorkspaceEditView({
					model: workspace,
					el: $('.mainarea', pages.workspaces)
				}));
			}

			if (workspace_id) {
				// Always fetch from the server before editing.
				this.setMainView(new GenericLoadingView({el: $('.mainarea', this.currentPage)}));

				this.breadcrumbs([
					{href: '/workspace/list', title: 'Workspaces'},
					{href: '#', title: 'Loading workspace ' + workspace_id + '...'}
				]);

				var workspace = new WorkspaceModel({'id': workspace_id});
				workspace.fetch({
					success: function(model, response, options) {
						workspaceEditInner(model);
					},
					error: _.bind(this.currentMainView.loadingError, this.currentMainView)
				});
			} else {
				// Load empty workspace.
				workspaceEditInner();
			}
		},

		workspaceList: function() {
			this.ensureVisible('workspaces');
			this.workspaceSetActive('');

			this.setMainView(new WorkspaceListView({
				collection: this.context.workspaces,
				el: $('.mainarea', this.currentPage)
			}));

			this.context.workspaces.fetch();

			this.breadcrumbs([{href: '/workspace/list', title: 'Workspaces'}]);

			this.currentMainView.render();
			this.currentMainView.startLoadingFull();
		},

		workspaceJobsList: function(workspace_id) {
			this.ensureVisible('workspaces');
			this.workspaceSetActive('workspace-' + workspace_id);

			var _self = this;
			this.fromCollectionOrServer(
				workspace_id,
				this.context.workspaces,
				WorkspaceModel,
				function (workspace) {
					var crumbs = [
						{href: '/workspace/list', title: 'Workspaces'},
						{href: '/workspace/' + workspace_id + '/applications', title: workspace.attributes.name}
					];

					var jobsUrl = window.location.pathname;
					var pageTitle = "All Jobs";
					if (window.location.search.indexOf('sub=cron') != -1) {
						crumbs.push({href: '', title: 'Cron Jobs'});
						jobsUrl += '?sub=cron&format=json';
						pageTitle = 'Cron Jobs';
					} else {
						crumbs.push({href: '', title: 'All Jobs'});
						jobsUrl += '?format=json';
					}

					_self.breadcrumbs(crumbs);

					_self.genericJobsListPage(jobsUrl, pageTitle);
				}
			);
		},

		applicationList: function(workspace_id) {
			this.ensureVisible('workspaces');
			this.workspaceSetActive('workspace-' + workspace_id);

			var _self = this;
			this.fromCollectionOrServer(
				workspace_id,
				this.context.workspaces,
				WorkspaceModel,
				function (workspace) {
					_self.breadcrumbs([
						{href: '/workspace/list', title: 'Workspaces'},
						{href: '/workspace/' + workspace_id + '/applications', title: workspace.attributes.name}
					]);

					_self.setMainView(new ApplicationListView({
						collection: workspace.applications,
						workspace: workspace,
						el: $('.mainarea', _self.currentPage)
					}));

					// Load from the server.
					workspace.applications.fetch();
				}
			);
		},

		applicationView: function(application_id) {
			this.ensureVisible('workspaces');
			this.workspaceSetActive('application-' + application_id);

			var _self = this;
			this.fromCollectionOrServer(
				application_id,
				this.context.applications,
				ApplicationModel,
				function (application) {
					_self.breadcrumbs([
						{href: '/workspace/list', title: 'Workspaces'},
						{
							href: '/workspace/' + application.attributes.workspace.id + '/applications',
							title: application.attributes.workspace.name
						},
						{
							href: '/application/' + application.id,
							title: application.attributes.name
						}
					]);

					_self.setMainView(new ApplicationDetailView({
						model: application,
						el: $('.mainarea', _self.currentPage)
					}));

					// Get the latest from the server.
					application.fetch();
					application.versions.fetch();
				}
			);
		},

		applicationServices: function(application_id) {
			this.ensureVisible('workspaces');
			this.workspaceSetActive('application-' + application_id);

			var _self = this;
			this.fromCollectionOrServer(
				application_id,
				this.context.applications,
				ApplicationModel,
				function (application) {
					_self.breadcrumbs([
						{href: '/workspace/list', title: 'Workspaces'},
						{
							href: '/workspace/' + application.attributes.workspace.id + '/applications',
							title: application.attributes.workspace.name
						},
						{
							href: '/application/' + application.id,
							title: application.attributes.name
						},
						{
							href: '/application/' + application.id + '/services',
							title: 'Services'
						}
					]);

					_self.genericDataTemplatePage(window.location.pathname + '?format=json', ApplicationServicesView);
				}
			);
		},

		applicationNew: function(workspace_id) {
			this.ensureVisible('workspaces');
			this.workspaceSetActive('create-application-' + workspace_id);

			var _self = this;
			this.fromCollectionOrServer(
				workspace_id,
				this.context.workspaces,
				WorkspaceModel,
				function (workspace) {
					_self.breadcrumbs([
						{href: '/workspace/list', title: 'Workspaces'},
						{href: '/workspace/' + workspace_id + '/applications', title: workspace.attributes.name},
						{href: '/workspace/' + workspace_id + '/applications/new', title: 'New Application'}
					]);

					_self.setMainView(new ApplicationNewView({
						url: window.location.pathname + '?format=json',
						workspace: workspace,
						newApplication: true,
						el: $('.mainarea', _self.currentPage)
					}));
				}
			);
		},

		applicationNewJob: function(workspace_id, job_id) {
			this.ensureVisible('workspaces');
			this.workspaceSetActive('create-application-' + workspace_id);

			var _self = this;
			this.fromCollectionOrServer(
				workspace_id,
				this.context.workspaces,
				WorkspaceModel,
				function (workspace) {
					_self.breadcrumbs([
						{href: '/workspace/list', title: 'Workspaces'},
						{href: '/workspace/' + workspace_id + '/applications', title: workspace.attributes.name},
						{
							href: window.location.pathname,
							title: "New Application"
						}
					]);

					_self.setMainView(new GenericJobView({
						job_id: job_id,
						el: $('.mainarea', _self.currentPage),
						finishedCallback: function(jid, state) {
							// When done, refresh the application that this belongs to.
							var workspace = _self.context.workspaces.get(workspace_id);
							workspace.applications.fetch();
						}
					}));
				}
			);
		},

		applicationJobsList: function(application_id) {
			this.ensureVisible('workspaces');
			this.workspaceSetActive('application-' + application_id);

			var _self = this;
			this.fromCollectionOrServer(
				application_id,
				this.context.applications,
				ApplicationModel,
				function (application) {
					var crumbs = [
						{href: '/workspace/list', title: 'Workspaces'},
						{href: '/workspace/' + application.attributes.workspace.id + '/applications', title: application.attributes.workspace.name},
						{href: '/application/' + application.id, title: application.attributes.name}
					];

					var jobsUrl = window.location.pathname;
					var pageTitle = "All Jobs";
					if (window.location.search.indexOf('sub=cron') != -1) {
						crumbs.push({href: '', title: 'Cron Jobs'});
						jobsUrl += '?sub=cron&format=json';
						pageTitle = 'Cron Jobs';
					} else {
						crumbs.push({href: '', title: 'All Jobs'});
						jobsUrl += '?format=json';
					}

					_self.breadcrumbs(crumbs);

					_self.genericJobsListPage(jobsUrl, pageTitle);
				}
			);
		},

		applicationNewVersion: function(application_id) {
			this.ensureVisible('workspaces');
			this.workspaceSetActive('create-version-' + application_id);

			var _self = this;
			this.fromCollectionOrServer(
				application_id,
				this.context.applications,
				ApplicationModel,
				function (application) {
					_self.breadcrumbs([
						{href: '/workspace/list', title: 'Workspaces'},
						{
							href: '/workspace/' + application.attributes.workspace.id + '/applications',
							title: application.attributes.workspace.name
						},
						{
							href: '/application/' + application.id,
							title: application.attributes.name
						},
						{href: window.location.pathname, title: 'New Version'}
					]);

					_self.setMainView(new ApplicationNewView({
						url: window.location.pathname + '?format=json',
						workspace: application.attributes.workspace,
						application: application,
						newApplication: false,
						el: $('.mainarea', _self.currentPage)
					}));
				}
			);
		},

		applicationNewVersionJob: function(application_id, job_id) {
			this.ensureVisible('workspaces');
			this.workspaceSetActive('create-version-' + application_id);

			var _self = this;
			this.fromCollectionOrServer(
				application_id,
				this.context.applications,
				ApplicationModel,
				function (application) {
					_self.breadcrumbs([
						{href: '/workspace/list', title: 'Workspaces'},
						{
							href: '/workspace/' + application.attributes.workspace.id + '/applications',
							title: application.attributes.workspace.name
						},
						{
							href: '/application/' + application.id,
							title: application.attributes.name
						},
						{
							href: window.location.pathname,
							title: "New Version"
						}
					]);

					_self.setMainView(new GenericJobView({
						job_id: job_id,
						el: $('.mainarea', _self.currentPage),
						finishedCallback: function(jid, state) {
							// When done, refresh the application that this belongs to.
							var workspace = _self.context.workspaces.get(application.attributes.workspace.id);
							workspace.applications.fetch();

							// And refresh the main application.
							var updatedApplication = _self.context.applications.get(application.id);
							updatedApplication.fetch();
						}
					}));
				}
			);
		},

		applicationDeleteJob: function(application_id, job_id) {
			this.ensureVisible('workspaces');
			this.workspaceSetActive('application-' + application_id);

			var _self = this;
			this.fromCollectionOrServer(
				application_id,
				this.context.applications,
				ApplicationModel,
				function (application) {
					_self.breadcrumbs([
						{href: '/workspace/list', title: 'Workspaces'},
						{
							href: '/workspace/' + application.attributes.workspace.id + '/applications',
							title: application.attributes.workspace.name
						},
						{
							href: '/application/' + application.attributes.id,
							title: application.attributes.name
						},
						{
							href: window.location.pathname,
							title: 'Delete'
						}
					]);

					_self.setMainView(new GenericJobView({
						job_id: job_id,
						el: $('.mainarea', _self.currentPage),
						finishedCallback: function(jid, state) {
							// When done, refresh the application that this belongs to.
							var workspace = _self.context.workspaces.get(application.attributes.workspace.id);
							workspace.applications.fetch();
						}
					}));
				}
			);
		},

		versionView: function(version_id) {
			this.ensureVisible('workspaces');
			this.workspaceSetActive('version-' + version_id);

			var _self = this;
			this.fromCollectionOrServer(
				version_id,
				this.context.versions,
				VersionModel,
				function (version) {
					_self.breadcrumbs([
						{href: '/workspace/list', title: 'Workspaces'},
						{
							href: '/workspace/' + version.attributes.workspace.id + '/applications',
							title: version.attributes.workspace.name
						},
						{
							href: '/application/' + version.attributes.application.id,
							title: version.attributes.application.name
						},
						{
							href: '/version/' + version.attributes.id,
							title: 'Version ' + version.attributes.version
						}
					]);

					_self.setMainView(new VersionDetailView({
						model: version,
						el: $('.mainarea', _self.currentPage)
					}));
				},
				function (version) {
					// If fetched from the collection, refresh from the server.
					version.fetch();
				}
			);
		},

		versionManifest: function(version_id) {
			this.ensureVisible('workspaces');
			this.workspaceSetActive('version-' + version_id);

			var _self = this;
			this.fromCollectionOrServer(
				version_id,
				this.context.versions,
				VersionModel,
				function (version) {
					_self.breadcrumbs([
						{href: '/workspace/list', title: 'Workspaces'},
						{
							href: '/workspace/' + version.attributes.workspace.id + '/applications',
							title: version.attributes.workspace.name
						},
						{
							href: '/application/' + version.attributes.application.id,
							title: version.attributes.application.name
						},
						{
							href: '/version/' + version.attributes.id,
							title: 'Version ' + version.attributes.version
						},
						{
							href: window.location.pathname,
							title: 'Manifest'
						}
					]);

					_self.genericDataTemplatePage(window.location.pathname + '?format=json', VersionManifestView);
				}
			);
		},

		versionLogView: function(version_id, log_id) {
			this.ensureVisible('workspaces');
			this.workspaceSetActive('version-' + version_id);

			var _self = this;
			this.fromCollectionOrServer(
				version_id,
				this.context.versions,
				VersionModel,
				function (version) {
					_self.breadcrumbs([
						{href: '/workspace/list', title: 'Workspaces'},
						{
							href: '/workspace/' + version.attributes.workspace.id + '/applications',
							title: version.attributes.workspace.name
						},
						{
							href: '/application/' + version.attributes.application.id,
							title: version.attributes.application.name
						},
						{
							href: '/version/' + version.attributes.id,
							title: 'Version ' + version.attributes.version
						},
						{
							href: window.location.pathname,
							title: 'Log File'
						}
					]);

					_self.setMainView(new GenericLogView({
						el: $('.mainarea', pages.workspaces),
						job_id: log_id,
						title: 'View log'
					}));
				}
			);
		},

		versionJobsList: function(version_id) {
			this.ensureVisible('workspaces');
			this.workspaceSetActive('version-' + version_id);

			var _self = this;
			this.fromCollectionOrServer(
				version_id,
				this.context.versions,
				VersionModel,
				function (version) {
					var crumbs = [
						{href: '/workspace/list', title: 'Workspaces'},
						{
							href: '/workspace/' + version.attributes.workspace.id + '/applications',
							title: version.attributes.workspace.name
						},
						{
							href: '/application/' + version.attributes.application.id,
							title: version.attributes.application.name
						},
						{
							href: '/version/' + version.attributes.id,
							title: 'Version ' + version.attributes.version
						}
					];

					var jobsUrl = window.location.pathname;
					var pageTitle = "All Jobs";
					if (window.location.search.indexOf('sub=cron') != -1) {
						crumbs.push({href: '', title: 'Cron Jobs'});
						jobsUrl += '?sub=cron&format=json';
						pageTitle = 'Cron Jobs';
					} else {
						crumbs.push({href: '', title: 'All Jobs'});
						jobsUrl += '?format=json';
					}

					_self.breadcrumbs(crumbs);

					_self.genericJobsListPage(jobsUrl, pageTitle);
				}
			);
		},

		jobActionMap: {
			'start': 'Start',
			'stop': 'Stop',
			'register': 'Register',
			'deregister': 'De-Register',
			'setcurrent': 'Make Current',
			'quantity': 'Instance Quantity'
		},

		versionJob: function(version_id, action, job_id) {
			this.ensureVisible('workspaces');
			this.workspaceSetActive('version-' + version_id);

			var _self = this;
			this.fromCollectionOrServer(
				version_id,
				this.context.versions,
				VersionModel,
				function (version) {
					_self.breadcrumbs([
						{href: '/workspace/list', title: 'Workspaces'},
						{
							href: '/workspace/' + version.attributes.workspace.id + '/applications',
							title: version.attributes.workspace.name
						},
						{
							href: '/application/' + version.attributes.application.id,
							title: version.attributes.application.name
						},
						{
							href: '/version/' + version.attributes.id,
							title: 'Version ' + version.attributes.version
						},
						{
							href: window.location.pathname,
							title: _self.jobActionMap[action]
						}
					]);

					_self.setMainView(new GenericJobView({
						job_id: job_id,
						el: $('.mainarea', _self.currentPage),
						finishedCallback: function(jid, state) {
							// When done, refresh the application that this belongs to.
							var workspace = _self.context.workspaces.get(version.attributes.workspace.id);
							workspace.applications.fetch();
						}
					}));
				}
			);
		},

		serviceExport: function(service_id) {
			this.ensureVisible('workspaces');

			this.setMainView(new GenericLoadingView({el: $('.mainarea', this.currentPage)}));

			this.breadcrumbs([
				{href: '#', title: 'Loading...'},
			]);

			var _self = this;
			function serviceExportInner(service) {
				_self.breadcrumbs([
					{href: '/workspace/list', title: 'Workspaces'},
					{
						href: '/workspace/' + service.attributes.workspace.id + '/applications',
						title: service.attributes.workspace.name
					},
					{
						href: '/application/' + service.attributes.application.id,
						title: service.attributes.application.name
					},
					{
						href: '/application/' + service.attributes.application.id + '/services',
						title: 'Services'
					},
					{
						href: '/service/export/' + service_id,
						title: 'Export service ' + service.attributes.name
					}
				]);

				_self.setMainView(new ServiceExportView({
					el: $('.mainarea', _self.currentPage),
					model: service
				}));
			}

			var service = new ServiceModel({'id': service_id});
			service.url = '/service/export/' + service_id + '?format=json';
			service.fetch({
				success: function(model, response, options) {
					serviceExportInner(model);
				},
				error: _.bind(this.currentMainView.loadingError, this.currentMainView)
			});
		},

		serviceImport: function(service_id) {
			this.ensureVisible('workspaces');

			this.setMainView(new GenericLoadingView({el: $('.mainarea', this.currentPage)}));

			this.breadcrumbs([
				{href: '#', title: 'Loading...'},
			]);

			var _self = this;
			function serviceImportInner(service) {
				_self.breadcrumbs([
					{href: '/workspace/list', title: 'Workspaces'},
					{
						href: '/workspace/' + service.attributes.workspace.id + '/applications',
						title: service.attributes.workspace.name
					},
					{
						href: '/application/' + service.attributes.application.id,
						title: service.attributes.application.name
					},
					{
						href: '/application/' + service.attributes.application.id + '/services',
						title: 'Services'
					},
					{
						href: '/service/import/' + service_id,
						title: 'Import service ' + service.attributes.name
					}
				]);

				_self.setMainView(new ServiceImportView({
					el: $('.mainarea', _self.currentPage),
					model: service
				}));
			}

			var service = new ServiceModel({'id': service_id});
			service.url = '/service/import/' + service_id + '?format=json';
			service.fetch({
				success: function(model, response, options) {
					serviceImportInner(model);
				},
				error: _.bind(this.currentMainView.loadingError, this.currentMainView)
			});
		},

		serviceImportJob: function(service_id, job_id) {
			this.ensureVisible('workspaces');

			this.setMainView(new GenericLoadingView({el: $('.mainarea', this.currentPage)}));

			this.breadcrumbs([
				{href: '#', title: 'Loading...'},
			]);

			var _self = this;
			function serviceImportJobInner(service) {
				_self.breadcrumbs([
					{href: '/workspace/list', title: 'Workspaces'},
					{
						href: '/workspace/' + service.attributes.workspace.id + '/applications',
						title: service.attributes.workspace.name
					},
					{
						href: '/application/' + service.attributes.application.id,
						title: service.attributes.application.name
					},
					{
						href: '/application/' + service.attributes.application.id + '/services',
						title: 'Services'
					},
					{
						href: '/service/import/' + service_id,
						title: 'Import service ' + service.attributes.name
					},
					{
						href: '#',
						title: 'Import Status'
					}
				]);

				_self.setMainView(new GenericJobView({
					job_id: job_id,
					el: $('.mainarea', _self.currentPage),
					title: 'Import Status'
				}));
			}

			var service = new ServiceModel({'id': service_id});
			service.url = '/service/import/' + service_id + '?format=json';
			service.fetch({
				success: function(model, response, options) {
					serviceImportJobInner(model);
				},
				error: _.bind(this.currentMainView.loadingError, this.currentMainView)
			});
		},

		nodeList: function() {
			this.ensureVisible('nodes');

			this.setMainView(new NodeListView({
				collection: this.context.nodes,
				el: $('.mainarea', pages.nodes)
			}));

			// Refresh the list of nodes.
			this.context.nodes.fetch();

			// Reset the active flag on all nodes.
			this.context.nodes.invoke('set', {active: false});

			this.breadcrumbs([{href: '/node/list', title: 'Nodes'}]);

			this.currentMainView.render();
			this.currentMainView.startLoadingFull();
		},

		nodeDetail: function(node_id) {
			this.ensureVisible('nodes');

			var _self = this;
			this.fromCollectionOrServer(
				node_id,
				this.context.nodes,
				NodeModel,
				function (node) {
					node.set({active: true});

					_self.breadcrumbs([
						{href: '/node/list', title: 'Nodes'},
						{href: '/node/' + node_id, title: node.attributes.name}
					]);

					_self.setMainView(new NodeDetailView({
						model: node,
						el: $('.mainarea', pages.nodes)
					}));
				}
			);
		},

		nodeLogView: function(node_id, log_id) {
			this.ensureVisible('nodes');

			var _self = this;
			this.fromCollectionOrServer(
				node_id,
				this.context.nodes,
				NodeModel,
				function (node) {
					_self.breadcrumbs([
						{href: '/node/list', title: 'Nodes'},
						{href: '/node/' + node_id, title: node.attributes.name},
						{href: '#', title: 'Log View'}
					]);

					_self.setMainView(new GenericLogView({
						el: $('.mainarea', pages.nodes),
						job_id: log_id,
						title: 'View log'
					}));
				}
			);
		},

		administrationList: function() {
			this.ensureVisible('administration');

			this.context.administrations.invoke('set', {active: false});

			this.breadcrumbs([
				{href: '/administration/list', title: 'Administration'}
			]);

			this.setMainView(new AdministrationListView({
				collection: this.context.administrations,
				el: $('.mainarea', pages.administration)
			}));
		},

		yourProfile: function() {
			this.ensureVisible('administration');

			this.breadcrumbs([
				{href: '/administration/list', title: 'Administration'},
				{href: '/profile', title: 'Your Profile'}
			]);

			this.adminSetActive();

			this.setMainView(new ProfileView({
				el: $('.mainarea', pages.administration)
			}));

			// Load the data manually.
			// TODO: Error handling.
			var _self = this;
			$.getJSON(
				'/profile?format=json',
				function(data)
				{
					_self.currentMainView.render(data.data.apikey);
				}
			);
		},

		userList: function() {
			this.ensureVisible('administration');

			this.adminSetActive();

			this.setMainView(new UserListView({
				collection: this.context.users,
				el: $('.mainarea', pages.administration)
			}));

			// Refresh the list of nodes.
			this.context.users.fetch();

			this.breadcrumbs([
				{href: '/administration/list', title: 'Administration'},
				{href: '/user/list', title: 'Users'}
			]);

			this.currentMainView.render();
			if (this.context.users.models.length == 0) {
				this.currentMainView.startLoadingFull();
			} else {
				this.currentMainView.startLoadingInline();
			}
		},

		userEdit: function(user_id) {
			this.ensureVisible('administration');
			this.adminSetActive('/user/list');

			var _self = this;
			function userEditInner(user) {
				var crumbs = [
					{href: '/administration/list', title: 'Administration'},
					{href: '/user/list', title: 'Users'}
				];
				if (user) {
					crumbs.push({href: '/user/' + user_id, title: 'Edit user ' + user.attributes.name});
				} else {
					crumbs.push({href: '/user/create', title: 'Create user'})
				}
				_self.breadcrumbs(crumbs);

				_self.setMainView(new UserEditView({
					model: user,
					el: $('.mainarea', pages.administration)
				}));
			}

			if (user_id) {
				// Always fetch from the server before editing.
				this.setMainView(new GenericLoadingView({el: $('.mainarea', pages.administration)}));

				this.breadcrumbs([
					{href: '/administration/list', title: 'Administration'},
					{href: '/user/list', title: 'Users'},
					{href: '#', title: 'Loading user ' + user_id + '...'}
				]);

				var user = new UserModel({'id': user_id});
				user.fetch({
					success: function(model, response, options) {
						userEditInner(model);
					},
					error: _.bind(this.currentMainView.loadingError, this.currentMainView)
				});
			} else {
				// Load empty user.
				userEditInner();
			}
		},

		roleList: function() {
			this.ensureVisible('administration');

			this.adminSetActive();

			this.setMainView(new RoleListView({
				collection: this.context.roles,
				el: $('.mainarea', pages.administration)
			}));

			// Refresh the list of roles.
			this.context.roles.fetch();

			this.breadcrumbs([
				{href: '/administration/list', title: 'Administration'},
				{href: '/role/list', title: 'Role List'}
			]);

			this.currentMainView.render();
			if (this.context.roles.models.length == 0) {
				this.currentMainView.startLoadingFull();
			} else {
				this.currentMainView.startLoadingInline();
			}
		},

		roleEdit: function(role_id) {
			this.ensureVisible('administration');
			this.adminSetActive('/role/list');

			var _self = this;
			function roleEditInner(role) {
				var crumbs = [
					{href: '/administration/list', title: 'Administration'},
					{href: '/role/list', title: 'Roles'}
				];
				if (role) {
					crumbs.push({href: '/role/' + role_id, title: 'Edit Role ' + role.attributes.name});
				} else {
					crumbs.push({href: '/role/create', title: 'Create role'})
				}
				_self.breadcrumbs(crumbs);

				_self.setMainView(new RoleEditView({
					model: role,
					el: $('.mainarea', pages.administration)
				}));
			}

			if (role_id) {
				// Always fetch from the server before editing.
				this.setMainView(new GenericLoadingView({el: $('.mainarea', pages.administration)}));

				this.breadcrumbs([
					{href: '/administration/list', title: 'Administration'},
					{href: '/role/list', title: 'Roles'},
					{href: '#', title: 'Loading role ' + role_id + '...'}
				]);

				var role = new RoleModel({'id': role_id});
				role.fetch({
					success: function(model, response, options) {
						roleEditInner(model);
					},
					error: _.bind(this.currentMainView.loadingError, this.currentMainView)
				});
			} else {
				// Load empty role.
				roleEditInner();
			}
		},

		roleAllocationList: function() {
			this.ensureVisible('administration');
			this.adminSetActive();

			this.setMainView(new RoleAllocationListView({
				collection: this.context.roleallocations,
				el: $('.mainarea', pages.administration)
			}));

			// Refresh the list of role allocations.
			this.context.roleallocations.fetch();

			this.breadcrumbs([
				{href: '/administration/list', title: 'Administration'},
				{href: '/role/allocation/list', title: 'Role Allocations'}
			]);

			this.currentMainView.render();
			if (this.context.roleallocations.models.length == 0) {
				this.currentMainView.startLoadingFull();
			} else {
				this.currentMainView.startLoadingInline();
			}
		},

		roleAllocationAssign: function() {
			this.ensureVisible('administration');
			this.adminSetActive('/role/allocation/list');

			this.breadcrumbs([
				{href: '/administration/list', title: 'Administration'},
				{href: '/role/allocation/list', title: 'Role Allocations'},
				{href: '/role/allocation/assign', title: 'Assign Role'}
			]);

			this.setMainView(new RoleAllocationAssignView({
				el: $('.mainarea', pages.administration)
			}));

			this.currentMainView.render();

			// Refresh all data from the server.
			this.context.roles.fetch();
			this.context.users.fetch();
			this.context.workspaces.fetch();
		},

		adminHealthJobs: function() {
			this.ensureVisible('administration');
			this.adminSetActive('/job/list/health');

			this.breadcrumbs([
				{href: '/administration/list', title: 'Administration'},
				{href: '/job/list/health', title: 'Health Checks'}
			]);

			this.genericJobsListPage('/job/list/health?format=json', 'Health Checks');
		},

		adminPeriodicJobs: function() {
			this.ensureVisible('administration');
			this.adminSetActive('/job/list/periodic');

			this.breadcrumbs([
				{href: '/administration/list', title: 'Administration'},
				{href: '/job/list/periodic', title: 'Periodic Tasks'}
			]);

			this.genericJobsListPage('/job/list/periodic?format=json', 'Periodic Tasks');
		},

		adminRouterDump: function() {
			this.ensureVisible('administration');
			this.adminSetActive();

			this.breadcrumbs([
				{href: '/administration/list', title: 'Administration'},
				{href: '/router/dump', title: 'Router Dump'}
			]);

			this.genericDataTemplatePage('/router/dump?format=json', RouterDumpView);
		},

		adminConfigurationDump: function() {
			this.ensureVisible('administration');
			this.adminSetActive();

			this.breadcrumbs([
				{href: '/administration/list', title: 'Administration'},
				{href: '/configuration/dump', title: 'Configuration Dump'}
			]);

			this.genericDataTemplatePage('/configuration/dump?format=json', ConfigurationDumpView);
		},

		adminPluginsDump: function() {
			this.ensureVisible('administration');
			this.adminSetActive();

			this.breadcrumbs([
				{href: '/administration/list', title: 'Administration'},
				{href: '/configuration/plugins', title: 'Plugins'}
			]);

			this.genericDataTemplatePage('/configuration/plugins?format=json', PluginsDumpView);
		},

		defaultAction: function(route, params) {
			this.ensureVisible('404');
		}
	});

	return AppRouter;
});
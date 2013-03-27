
if (!window.pm) { var pm = {}; }	// TODO: module handling
if (!pm.jobs) { pm.jobs = {}; }

pm.jobs.list = (function() {
	return {
		render: {
			app_nav: function(data) {
				pm.leftmenu.redrawContainers();

				var parent_search = {};
				parent_search[data.object_details[0] + "_id"] = data.object_details[1];
				
				parent_search.callback = function(parents) {
						pm.leftmenu.updateAppMenu(parents.workspace.id, parent_search);
						pm.leftmenu.updateBreadcrumbs({
							workspace: parents.workspace,
							application: parents.application,
							version: parents.version,
							suffix: data.breadcrumb_suffix
						});
					}
				
				pm.data.api({
					endpoint: data.object_details.join('/'),
					callback: function(object_data) {
						if (object_data.workspace) {
							data.title = "Jobs: " + object_data.workspace.name;
						}
						if (object_data.application) {
							data.title = "Jobs: " + object_data.application.name;
						}
						if (object_data.version) {
							data.title = "Jobs: Version " + object_data.version.version;
						}
					
						pm.jobs.list.render.all(data);
						pm.data.get_app_parents(parent_search);
						$('.loading-overlay').remove();
					}
				});
			},
			
			instancetype: function(data) {
				// TODO: this isn't exposed anywhere in the interface
				pm.jobs.list.render.all(data);
			},
			
			node: function(data) {
				pm.leftmenu.redrawContainers();
				pm.node.list.updateNodeMenu(data.object_details[1]);

				pm.data.api({
					endpoint: 'node/' + data.object_details[1],
					callback: function(node_data) {
						data.title = "Node <code class=\"uuid-shrink\" title=\"" + node_data.node.uuid + "\"></code>";
						pm.jobs.list.render.all(data);
						
						pm.widgets.uuid.update();
						pm.node.list.updateBreadcrumbs(node_data);
						$('.loading-overlay').remove();
					}
				});
			},
			
			all: function(data) {
				$(data.render_container).html(pm.handlebars.job_list(data));
				
				$('.job-root').each(function(i, el) {
					new pm.jobs.display($(el));
				});
			}
		},
	
		switchTo: function() {
			var url_match = document.location.pathname.match(/^\/job\/list\/(.+)\/?$/);
			var object_details = url_match[1].split('/');

			pm.data.api({
				endpoint: document.location.pathname + document.location.search,
				callback: function(data) {
					var draw_function;
				
					switch (object_details[0]) {
						case "workspace":
						case "application":
						case "version":
							data.show_breadcrumbs = true;
							data.object_details = object_details;
							if (document.location.search.indexOf('cron') !== -1) {
								data.breadcrumb_suffix = "Cron Jobs";
							} else {
								data.breadcrumb_suffix = "All Jobs";
							}
							
							data.render_container = '#main_right_view';
							draw_function = pm.jobs.list.render.app_nav;
							break;
							
						case "instancetype":
							data.title = "Jobs for Instance Type";
							data.render_container = '#main';
							draw_function = pm.jobs.list.render.all;
							break;
						
						case "node":
							data.show_breadcrumbs = true;
							data.object_details = object_details;
							data.render_container = '#main_right_view';
							draw_function = pm.jobs.list.render.node;
							break;
						
						case "health":
							data.title = "Health Checks";
							data.render_container = '#main';
							draw_function = pm.jobs.list.render.all;
							break;
							
						case "periodic":
							data.title = "Systemwide Periodic Tasks";
							data.render_container = '#main';
							draw_function = pm.jobs.list.render.all;
							break;
					}
					
					draw_function.apply(this, [data]);
				}
			});
		}
	};
}());


pm.jobs.summary = (function() {
	return {
		renderSummaryTree: function(job_id, tree_item) {
			var el = $('li[rel=' + job_id + ']');
			if (el.length) {
				$('a.title', el).text(tree_item.title);
				$('span.state', el).attr('data-state', tree_item.state);
				pm.jobs.display.prototype.setStateClass($('span.state', el), tree_item.state)
				pm.jobs.display.prototype.setStateIcon($('span.state', el), tree_item.state)
			}
		},

		show: function(container, job_ids) {
			pm.data.subscribe(
				'job.status',
				function(job_id, status) {
					console.log(job_id, status);
					var el = $('li[rel=' + job_id + '] span.state');
					if (el.length) {
						el.attr('data-state', status.state);	// TODO: use .data() instead?
						pm.jobs.display.prototype.setStateClass(el, status.state)
						pm.jobs.display.prototype.setStateIcon(el, status.state)
					}
				}
			);

			pm.data.subscribe(
				'job.tree',
				function(job_id, tree) {
					//if(job_ids.indexOf(job_id) !== -1) {
						pm.jobs.summary.renderSummaryTree(job_id, tree);
					//}
				}
			);

			if (job_ids.length == 0) {
				container.append("<li>No recent jobs to show</li>");
			}

			job_ids.forEach(function(job_id) {
				var details = $('<li>');
				details.append($('<span class="state"></span>'));
				details.append($('<a href="/job/detail/' + job_id + '" class="title"></a>'));
				details.addClass('details');
				details.attr('rel', job_id);	// TODO: use .data() instead?
				container.append(details);

				pm.data.emit('job.subscribe', job_id);
			});
		}

	};
}());

pm.jobs.single = (function() {
	return {
		switchTo: function(state) {
			pm.leftmenu.redrawContainers();

			if (state.job_id) {
				var job_id = state.job_id;
			} else {
				// read job ID from the URL if it wasn't passed in
				var url_match = document.location.pathname.match(/^\/job\/detail\/([0-9a-f\-]+)\/?$/);
				var job_id = url_match[1];
			}

			var job_well = $("<div>");
			job_well.addClass("job-root well well-small");
			job_well.attr("data-job", job_id);

			$('#main_right_view').append(job_well);
			
			if (state.version_id || state.application_id || state.workspace_id) {
				// redraw breadcrumbs if we came from app navigation and had details passed in
				$('#main_right_view').prepend($('<ul class="breadcrumb">'));

				state.callback = function(parents) {
					pm.leftmenu.updateBreadcrumbs({
						workspace: parents.workspace,
						application: parents.application,
						version: parents.version,
						suffix: "Job " + job_id
					});
				};
				
				pm.data.get_app_parents(state);

			} else if (state.node) {
				// also redraw breadcrumbs if we came from a node details page
				$('#main_right_view').prepend($('<ul class="breadcrumb">'));
				pm.node.list.updateBreadcrumbs(state);

			} else {
				$('#main_right_view').prepend($('<h1>Job Detail</h1>'));
			}

			new pm.jobs.display(job_well);
			$('.loading-overlay').remove();
		}
	};
}());

pm.jobs.display = function(container) {
	this.container = container;
	this.job_id = container.attr('data-job');
	this.logSubscribed = {};

	var _self = this;

	// Subscribe to the events we want.
	pm.data.subscribe('job.tree',
		function(job_id, tree) {
			if(_self.job_id == job_id) {
				_self.renderJobTree([tree], 0);
			}
		}
	);

	pm.data.subscribe('job.new', function(data) {
		_self.newJob(data);
	});

	pm.data.subscribe('job.status',
		function(job_id, status) {
			_self.updateStatus(status);
		}
	);

	pm.data.subscribe('log.lines',
		function(job_id, lines, position) {
			if(_self.logSubscribed[job_id]) {
				_self.handleNewLines(job_id, lines, position);
			}
		}
	);

	pm.data.subscribe('log.zerosize',
		function(job_id) {
			if(_self.logSubscribed[job_id]) {
				_self.handleZeroSizeLog(job_id);
			}
		}
	);

	pm.data.emit('job.subscribe', this.job_id);
}

pm.jobs.display.prototype.handleZeroSizeLog = function(job_id)
{
	var container = $('.' + job_id + ' .log', this.container);
	container.html("No log entries for this job.")
	container.addClass('no-data');
}

pm.jobs.display.prototype.isScrolledToBottom = function(el) {
	var content_height = el[0].scrollHeight;
	var current_view_bottom = el[0].scrollTop + el.innerHeight();
	return (content_height == current_view_bottom);
}

pm.jobs.display.prototype.handleNewLines = function(job_id, lines, position)
{
	var container = $('.' + job_id + ' .log', this.container);
	container.removeClass('no-data');
	var formatted = this.formatLogLines(lines.join(''));

	if (this.isScrolledToBottom(container)) { var reset_scroll = true; }

	container.append(formatted);
	container.attr('data-position', position);

	if (reset_scroll) {
		// TODO: test this across browsers
		container[0].scrollTop = container[0].scrollHeight;
	}
}

pm.jobs.display.prototype.renderJobTree = function(tree, level, container)
{
	// Empty out the container.
	var workingContainer = this.container;
	if( container )
	{
		workingContainer = container;
	}
	workingContainer.empty();

	// Sort my tree by time.
	tree.sort(function(a, b) {
		return a.time - b.time;
	});

	var _self = this;
	$.each(tree, function(index, element)
	{
		var thisContainer = _self.createContainer(element.job_id, level, element);
		workingContainer.append(thisContainer);
	});
}

pm.jobs.display.prototype.newJob = function(data)
{
	// Find the parent container.
	var parentId = data['parent_id'];
	var parentChildContainer = $('.children-' + parentId, this.container);
	var levelParent = parseInt(parentChildContainer.parent().attr('data-level'), 10) + 1;
	var newJobContainer = this.createContainer(data.job_id, levelParent, data);
	parentChildContainer.append(newJobContainer);
}

pm.jobs.display.prototype.createContainer = function(job_id, level, data)
{
	var thisJobContainer = $('<div class="job-status level' + level + '"></div>');
	thisJobContainer.attr('data-level', level);

	var details = $('<div class="details"></div>');
	details.addClass(job_id);
	details.append($('<span class="state"></span>'));
	details.append($('<span class="toolbox"></span>'));
	details.append($('<span class="title"></span>'));
	details.append($('<span class="summary"></span>'));
	// details.append($('<span class="time"></span>'));
	details.append($('<pre class="log"></pre>'));
	thisJobContainer.append(details);

	var childrenContainer = $('<div class="children"></div>');
	childrenContainer.addClass('children-' + job_id);
	thisJobContainer.append(childrenContainer);

	var title = data.title;
	if (/[0-9T\-\:\.]{26}/.test(title)) {
		// TODO: this is hackish, but for now the timestamp is embedded at the end of
		// the title string for each job; parse it out and reformat using moment.js
		var raw_date = title.substr(-26);
		var moment = pm.util.formatDate(raw_date);

		// remove old unformatted date, and "at" if present
		title = title.substring(0, title.length - 26);
		if (title.substr(-4) == " at ") { title = title.substring(0, title.length - 3); }
		title += " <span title=\"" + raw_date + "\">" + moment.calendar + "</span>";
	}
	$('.title', thisJobContainer).html(title);

	if( data.summary && data.state != 'SUCCESS' )
	{
		$('.summary', thisJobContainer).text('Summary: ' + data.summary);
	}
	else
	{
		$('.summary', thisJobContainer).text('');
	}

	/*var thisTime = new Date();
	thisTime.setTime(data.time * 1000);
	$('.time', thisJobContainer).text(thisTime.toString());*/

	var stateContainer = $('.state', thisJobContainer);
	this.setStateClass(stateContainer, data.state);
	this.setStateIcon(stateContainer, data.state);
	var logContainer = $('.log', thisJobContainer);

	var toolbox = $('.toolbox', thisJobContainer);
	var _self = this;
	if( false == toolbox.hasClass('populated') )
	{
		// Populate and hook up the toolbox.
		var logExpander = $('<a href="#" title="View log for this job"><i class="icon-list"></i></a>');
		logExpander.click(
			function(e)
			{
				_self.toggleSubscribeLog(data.job_id, logContainer);

				e.preventDefault();
			}
		);
		toolbox.append(logExpander);

		if( data.state != 'SUCCESS' && data.state != 'FAILED' && data.state != 'ABORTED' )
		{
			var aborter = $('<a class="aborter" href="#" title="Abort Job"><i class="icon-off"></i></a>');
			aborter.click(
				function(e)
				{
					$.getJSON(
						'/job/abort/' + job_id + '?format=json',
						function( data )
						{
							// No action to date.
							console.log(data);
						}
					);
					e.preventDefault();
				}
			);
			toolbox.append(aborter);
		}

		toolbox.addClass('populated');
	}

	// Recurse into the children.
	if( data.children )
	{
		var childContainer = $('.children', thisJobContainer);
		_self.renderJobTree(data.children, level + 1, childContainer);
	}

	return thisJobContainer;
}

BOOTSTRAP_CLASS_MAP = {
	'FAILED': 'important', // Er, ok.
	'ABORTED': 'warning',
	'SUCCESS': 'success',
	'WAITING': 'info',
	'RUNNING': 'primary'
}

BOOTSTRAP_ICON_MAP = {
	'FAILED': 'icon-remove',
	'ABORTED': 'icon-ban-circle',
	'SUCCESS': 'icon-ok',
	'WAITING': 'icon-time',
	'RUNNING': 'icon-loading',
	'NEW': 'icon-certificate'
}

pm.jobs.display.prototype.setStateClass = function(element, state)
{
	var oldState = element.attr('data-state');
	if( oldState )
	{
		element.removeClass('state-' + oldState);
		var oldBootstrapClass = BOOTSTRAP_CLASS_MAP[oldState];
		if( oldBootstrapClass )
		{
			element.removeClass('label-' + oldBootstrapClass);
		}
	}
	element.addClass('state-' + state);
	element.attr('data-state', state);

	// And add a class that inherits a bootstrap colour.
	var bootstrapClass = BOOTSTRAP_CLASS_MAP[state];
	if( !bootstrapClass )
	{
		bootstrapClass = 'default';
	}

	element.addClass('label');
	element.addClass('label-' + bootstrapClass);
}

pm.jobs.display.prototype.setStateIcon = function(element, state)
{
	var icon = $('<i></i>');

	var oldState = element.attr('data-state');
	if( oldState )
	{
		element.removeClass('state-' + oldState);
		var oldBootstrapClass = BOOTSTRAP_ICON_MAP[oldState];
		if( oldBootstrapClass )
		{
			element.removeClass('label-' + oldBootstrapClass);
		}
	}

	icon.addClass('icon-white');
	icon.addClass(BOOTSTRAP_ICON_MAP[state]);

	element.html(icon);
}

pm.jobs.display.prototype.updateStatus = function(status)
{
	// Find the appropriate status element.
	var el = $('.' + status.job_id + ' .state', this.container);
	this.setStateClass(el, status.state);
	this.setStateIcon(el, status.state);
	el.attr('data-state', status.state);

	if( status.state == 'SUCCESS' || status.state == 'FAILED' || status.state == 'ABORTED' )
	{
		// Remove the abort button, if present.
		$('.' + status.job_id + ' .aborter', this.container).remove();
	}

	if( status.summary && status.state != 'SUCCESS' )
	{
		var summaryEl = $('.' + status.job_id + ' .summary', this.container);
		summaryEl.text('Summary: ' + status.summary);
	}
}

pm.jobs.display.prototype.toggleSubscribeLog = function(job_id, container)
{
	if( this.logSubscribed[job_id] )
	{
		container.slideUp();
		pm.data.emit('log.unsubscribe', job_id);
		this.logSubscribed[job_id] = false;
	}
	else
	{
		var position = container.attr('data-position');
		this.logSubscribed[job_id] = true;
		pm.data.emit('log.subscribe', job_id, position);
		container.slideDown();
	}
}

// TODO: This is duplicated code. Refactor this so it isn't.
pm.jobs.display.prototype.formatLogLines = function(lines)
{
	var LOG_LEVEL_MAP = [
		['DEBUG', 'label'],
		['INFO', 'label label-info'],
		['WARNING', 'label label-warning'],
		['ERROR', 'label label-important'],
		['CRITICAL', 'label label-important']
	]

	var output = lines;
	output = htmlEscape(output);
	for( var i = 0; i < LOG_LEVEL_MAP.length; i++ )
	{
		output = output.replace(
			new RegExp('\\s' + LOG_LEVEL_MAP[i][0] + '\\s', 'g'),
			' <span class="' + LOG_LEVEL_MAP[i][1] + '">' + LOG_LEVEL_MAP[i][0] + '</span> '
		);
	}
	return output;
}
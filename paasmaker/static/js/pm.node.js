/**
 * Paasmaker 0.9.0
 * Insert licence notice here
 *
 * pm.node.js - interfaces for viewing the list of nodes, and individual nodes
 */

if (!window.pm) { var pm = {}; }	// TODO: module handling
if (!pm.node) { pm.node = {}; }

pm.node.list = (function() {
	return {

		switchTo: function() {
			pm.data.template_from_api({
				endpoint: 'node/list',
				element: '#main',
				template: pm.handlebars.node_list,
				callback: function() {
					pm.widgets.uuid.update();
				}
			});
		}
		
	};
}());


pm.node.detail = (function() {

	return {
		uptimeString: function(start_time) {
			var uptime = moment().diff(start_time, 'seconds');
			var uptime_string = '';
			if (uptime > 86400) {
				uptime_string += Math.floor(uptime/86400) + " days, ";
				uptime = uptime % 86400;
			}
			if (uptime > 3600) {
				uptime_string += Math.floor(uptime/3600) + " hours, ";
				uptime = uptime % 3600;
			}
			if (uptime > 60) {
				uptime_string += Math.floor(uptime/60) + " minutes, ";
				uptime = uptime % 60;
			}
			uptime_string += uptime + " seconds";
			
			return uptime_string;
		},
	
		processNodeData: function(data) {
			data.formatted_tags = JSON.stringify(data.tags, undefined, 4);
			data.formatted_stats = JSON.stringify(data.stats, undefined, 4);

			var last_heard = pm.util.parseDate(data.last_heard);
			data.formatted_last_heard = last_heard.format(pm.util.date_formats.word);
			data.updated_age = moment().diff(last_heard, 'seconds');

			var start_time = pm.util.parseDate(data.start_time);
			data.formatted_start_time = start_time.format(pm.util.date_formats.word);
			data.uptime_string = pm.node.detail.uptimeString(start_time);
			
			data.formatted_score = data.score.toFixed(2);
			
			if (data.tags.runtimes && Object.keys(data.tags.runtimes).length > 0) {
				data.runtimes = [];
				for (var name in data.tags.runtimes) {
					data.runtimes.push({
						name: name,
						versions: data.tags.runtimes[name].join(', ')
					});
				}
			}
			
			return data;		
		},

		switchTo: function() {
			var url_match = document.location.pathname.match(/\/(\d+)\/?$/);

// 			if ($('#app_menu_wrapper a').length && $('#app_view_main').length) {
// 				$('#app_view_main').empty();
// 			} else {
// 				$('#main').empty();
// 				$('#main').append(
// 					$("<div id=\"app_menu_wrapper\">"),
// 					$("<div id=\"app_view_main\" class=\"with-application-list\">")
// 				);
// 				pm.history.loadingOverlay("#app_view_main");
// 			}

			pm.data.api({
				endpoint: 'node/' + url_match[1],
				callback: function(data) {
					var node = pm.node.detail.processNodeData(data.node);

					$('#main').html(pm.handlebars.node_detail(node));
					
					pm.data.api({
						endpoint: 'node/' + url_match[1] + '/instances',
						callback: function(instance_data) {
							instance_data.instances.forEach(function(instance) {
								$('table.node-instances').append(pm.handlebars.node_instance_row(instance));
							});
							
							// after rendering instances, set up expandable UUIDs
							// and add event handlers for viewing logs
							// TODO: this is shared with pm.version.js
							pm.widgets.uuid.update();
							$('.instance-log-container').each(function(i, element) {
									new pm.logs.instance(streamSocket, $(element).attr('data-instance'));
							});
						}
					});
					
					$.plot('.node-disk .chart', [
						{ label: "Disk used", color: "darkviolet", data: (node.stats.disk_total - node.stats.disk_free) },
						{ label: "Disk free", color: "lightblue", data: node.stats.disk_free }
					], { series: { pie: { show: true } }, legend: { container: '.node-disk .legend' } });
					$.plot('.node-memory .chart', [
						{ label: "Memory used", color: "darksalmon", data: (node.stats.mem_total - node.stats.mem_adjusted_free) },
						{ label: "Memory free", color: "lightblue", data: node.stats.mem_adjusted_free }
					], { series: { pie: { show: true } }, legend: { container: '.node-memory .legend' } });
				}
			});
		}
	};
}());

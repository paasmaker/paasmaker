define([
	'underscore',
	'backbone',
	'util',
	'collections/instances'
], function(_, Backbone, util, InstancesCollection){
	var NodeModel = Backbone.Model.extend({
		initialize: function() {
			// Create an instances collection for this node.
			// Don't load it until we need to though.
			this.instances = new InstancesCollection();
			this.instances.url = '/node/' + this.id + '/instances?format=json';
		},
		defaults: {
			name: "none",
			uuid: "none"
		},
		url: function() {
			return '/node/' + this.id + '?format=json';
		},
		parse: function(data) {
			if(data.data) {
				// To handle the case where we fetch the response from the server directly.
				return data.data.node;
			} else {
				// To handle when the collection sends us data.
				return data;
			}
		},

		uptimeString: function(startTime) {
			if (!startTime) {
				startTime = util.parseDate(this.attributes.start_time);
			}
			var uptime = moment().diff(startTime, 'seconds');
			var uptimeString = '';
			if (uptime > 86400) {
				var days = Math.floor(uptime/86400);
				uptimeString += days + (days == 1 ? " day, " : " days, ");
				uptime = uptime % 86400;
			}
			if (uptime > 3600) {
				var hours = Math.floor(uptime/3600);
				uptimeString += hours + (hours == 1 ? " hour, " : " hours, ");
				uptime = uptime % 3600;
			}
			if (uptime > 60) {
				var minutes = Math.floor(uptime/60);
				uptimeString += minutes + (minutes == 1 ? " minute, " : " minutes, ");
				uptime = uptime % 60;
			}
			uptimeString += uptime + (uptime == 1 ? " second" : " seconds");

			return uptimeString;
		},

		runtimeSummary: function() {
			var runtimes = [];
			if (this.attributes.tags.runtimes && Object.keys(this.attributes.tags.runtimes).length > 0) {
				for (var name in this.attributes.tags.runtimes) {
					runtimes.push({
						name: name,
						versions: this.attributes.tags.runtimes[name].join(', ')
					});
				}
			}
			return runtimes;
		}
	});

	return NodeModel;
});
define([
	'underscore',
	'backbone',
	'util'
], function(_, Backbone, util){
	var NodeModel = Backbone.Model.extend({
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
		}
	});

	return NodeModel;
});
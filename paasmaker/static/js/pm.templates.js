(function() {
  var template = Handlebars.template, templates = Handlebars.templates = Handlebars.templates || {};
templates['node_delete'] = template(function (Handlebars,depth0,helpers,partials,data) {
  this.compilerInfo = [2,'>= 1.0.0-rc.3'];
helpers = helpers || Handlebars.helpers; data = data || {};
  var buffer = "", stack1, functionType="function", escapeExpression=this.escapeExpression;


  buffer += "<div id=\"node_delete_modal\" class=\"modal hide fade\" tabindex=\"-1\" role=\"dialog\" aria-labelledby=\"Delete Node\" aria-hidden=\"true\">\n  <div class=\"modal-header\">\n    <button type=\"button\" class=\"close\" data-dismiss=\"modal\" aria-hidden=\"true\">×</button>\n    <h3>Delete Node</h3>\n  </div>\n  <div class=\"modal-body\">\n	<p>Are you sure you want to delete ";
  if (stack1 = helpers.name) { stack1 = stack1.call(depth0, {hash:{},data:data}); }
  else { stack1 = depth0.name; stack1 = typeof stack1 === functionType ? stack1.apply(depth0) : stack1; }
  buffer += escapeExpression(stack1)
    + "?</p>\n	<p>This action cannot be undone.</p>\n  </div>\n  <div class=\"modal-footer\">\n    <button class=\"btn\" data-dismiss=\"modal\" aria-hidden=\"true\">Cancel</button>\n		<form method=\"POST\" action=\"/node/";
  if (stack1 = helpers.id) { stack1 = stack1.call(depth0, {hash:{},data:data}); }
  else { stack1 = depth0.id; stack1 = typeof stack1 === functionType ? stack1.apply(depth0) : stack1; }
  buffer += escapeExpression(stack1)
    + "/delete\" style=\"display: inline;\">\n			<input type=\"submit\" class=\"btn btn-primary btn-danger\" value=\"Delete Node\" />\n		</form>\n  </div>\n</div>";
  return buffer;
  });
})();(function() {
  var template = Handlebars.template, templates = Handlebars.templates = Handlebars.templates || {};
templates['node_instance_row'] = template(function (Handlebars,depth0,helpers,partials,data) {
  this.compilerInfo = [2,'>= 1.0.0-rc.3'];
helpers = helpers || Handlebars.helpers; data = data || {};
  var buffer = "", stack1, stack2, functionType="function", escapeExpression=this.escapeExpression;


  buffer += "<tr>\n	<td class=\"contains-uuid\">\n		<code class=\"uuid-shrink\" title=\"";
  if (stack1 = helpers.instance_id) { stack1 = stack1.call(depth0, {hash:{},data:data}); }
  else { stack1 = depth0.instance_id; stack1 = typeof stack1 === functionType ? stack1.apply(depth0) : stack1; }
  buffer += escapeExpression(stack1)
    + "\"></code>\n	</td>\n	<td>\n		<a href=\"/application/"
    + escapeExpression(((stack1 = ((stack1 = depth0.application),stack1 == null || stack1 === false ? stack1 : stack1.id)),typeof stack1 === functionType ? stack1.apply(depth0) : stack1))
    + "\">\n			"
    + escapeExpression(((stack1 = ((stack1 = depth0.application),stack1 == null || stack1 === false ? stack1 : stack1.name)),typeof stack1 === functionType ? stack1.apply(depth0) : stack1))
    + "\n		</a>\n	</td>\n	<td>\n		<a href=\"/version/"
    + escapeExpression(((stack1 = ((stack1 = depth0.version),stack1 == null || stack1 === false ? stack1 : stack1.id)),typeof stack1 === functionType ? stack1.apply(depth0) : stack1))
    + "\">\n			Version "
    + escapeExpression(((stack1 = ((stack1 = depth0.version),stack1 == null || stack1 === false ? stack1 : stack1.version)),typeof stack1 === functionType ? stack1.apply(depth0) : stack1))
    + "\n		</a>\n	</td>\n	<td>\n		";
  if (stack2 = helpers.state) { stack2 = stack2.call(depth0, {hash:{},data:data}); }
  else { stack2 = depth0.state; stack2 = typeof stack2 === functionType ? stack2.apply(depth0) : stack2; }
  buffer += escapeExpression(stack2)
    + "\n	</td>\n	<td class=\"instance-log-button\">\n		<a href=\"#\" class=\"btn btn-mini toggle ";
  if (stack2 = helpers.instance_id) { stack2 = stack2.call(depth0, {hash:{},data:data}); }
  else { stack2 = depth0.instance_id; stack2 = typeof stack2 === functionType ? stack2.apply(depth0) : stack2; }
  buffer += escapeExpression(stack2)
    + "\"><i class=\"icon-list\"></i> View Log</a>\n	</td>\n</tr>\n<tr>\n	<td colspan=\"5\" class=\"instance-log-container ";
  if (stack2 = helpers.instance_id) { stack2 = stack2.call(depth0, {hash:{},data:data}); }
  else { stack2 = depth0.instance_id; stack2 = typeof stack2 === functionType ? stack2.apply(depth0) : stack2; }
  buffer += escapeExpression(stack2)
    + "\" data-instance=\"";
  if (stack2 = helpers.instance_id) { stack2 = stack2.call(depth0, {hash:{},data:data}); }
  else { stack2 = depth0.instance_id; stack2 = typeof stack2 === functionType ? stack2.apply(depth0) : stack2; }
  buffer += escapeExpression(stack2)
    + "\">\n	</td>\n</tr>";
  return buffer;
  });
})();(function() {
  var template = Handlebars.template, templates = Handlebars.templates = Handlebars.templates || {};
templates['node_detail'] = template(function (Handlebars,depth0,helpers,partials,data) {
  this.compilerInfo = [2,'>= 1.0.0-rc.3'];
helpers = helpers || Handlebars.helpers; data = data || {};
  var buffer = "", stack1, functionType="function", escapeExpression=this.escapeExpression, self=this;

function program1(depth0,data) {
  
  
  return "\n		<a href=\"#\" class=\"btn disabled\">\n			<i class=\"icon-calendar\"></i> Pacemaker\n		</a>\n	";
  }

function program3(depth0,data) {
  
  
  return "\n		<a href=\"#\" class=\"btn disabled\">\n			<i class=\"icon-heart\"></i> Heart\n		</a>\n	";
  }

function program5(depth0,data) {
  
  
  return "\n		<a href=\"#\" class=\"btn disabled\">\n			<i class=\"icon-random\"></i> Router\n		</a>\n	";
  }

function program7(depth0,data) {
  
  var buffer = "", stack1;
  buffer += "\n	<table class=\"table table-bordered node-runtime\">\n		<tr class=\"node-table-header\">\n			<th>Runtimes</th>\n			<th>Version(s)</th>\n		</tr>\n		";
  stack1 = helpers.each.call(depth0, depth0.runtimes, {hash:{},inverse:self.noop,fn:self.program(8, program8, data),data:data});
  if(stack1 || stack1 === 0) { buffer += stack1; }
  buffer += "\n	</table>\n";
  return buffer;
  }
function program8(depth0,data) {
  
  var buffer = "", stack1;
  buffer += "\n			<tr>\n				<td>";
  if (stack1 = helpers.name) { stack1 = stack1.call(depth0, {hash:{},data:data}); }
  else { stack1 = depth0.name; stack1 = typeof stack1 === functionType ? stack1.apply(depth0) : stack1; }
  buffer += escapeExpression(stack1)
    + "</td>\n				<td>";
  if (stack1 = helpers.versions) { stack1 = stack1.call(depth0, {hash:{},data:data}); }
  else { stack1 = depth0.versions; stack1 = typeof stack1 === functionType ? stack1.apply(depth0) : stack1; }
  buffer += escapeExpression(stack1)
    + "</td>\n			</tr>\n		";
  return buffer;
  }

  buffer += "<ul class=\"breadcrumb\"></ul>\n\n<h1>\n	Node ";
  if (stack1 = helpers.name) { stack1 = stack1.call(depth0, {hash:{},data:data}); }
  else { stack1 = depth0.name; stack1 = typeof stack1 === functionType ? stack1.apply(depth0) : stack1; }
  buffer += escapeExpression(stack1)
    + "\n\n	";
  stack1 = helpers['if'].call(depth0, depth0.pacemaker, {hash:{},inverse:self.noop,fn:self.program(1, program1, data),data:data});
  if(stack1 || stack1 === 0) { buffer += stack1; }
  buffer += "\n	";
  stack1 = helpers['if'].call(depth0, depth0.heart, {hash:{},inverse:self.noop,fn:self.program(3, program3, data),data:data});
  if(stack1 || stack1 === 0) { buffer += stack1; }
  buffer += "\n	";
  stack1 = helpers['if'].call(depth0, depth0.router, {hash:{},inverse:self.noop,fn:self.program(5, program5, data),data:data});
  if(stack1 || stack1 === 0) { buffer += stack1; }
  buffer += "\n</h1>\n\n<div class=\"node-chart node-disk\">\n	<div class=\"chart\"></div><div class=\"legend\"></div>\n</div>\n<div class=\"node-chart node-memory\">\n	<div class=\"chart\"></div><div class=\"legend\"></div>\n</div>\n\n<ul class=\"node-details\">\n	<li><strong>UUID:</strong> <code>";
  if (stack1 = helpers.uuid) { stack1 = stack1.call(depth0, {hash:{},data:data}); }
  else { stack1 = depth0.uuid; stack1 = typeof stack1 === functionType ? stack1.apply(depth0) : stack1; }
  buffer += escapeExpression(stack1)
    + "</code></li>\n	<li><strong>Route:</strong> ";
  if (stack1 = helpers.route) { stack1 = stack1.call(depth0, {hash:{},data:data}); }
  else { stack1 = depth0.route; stack1 = typeof stack1 === functionType ? stack1.apply(depth0) : stack1; }
  buffer += escapeExpression(stack1)
    + ":";
  if (stack1 = helpers.apiport) { stack1 = stack1.call(depth0, {hash:{},data:data}); }
  else { stack1 = depth0.apiport; stack1 = typeof stack1 === functionType ? stack1.apply(depth0) : stack1; }
  buffer += escapeExpression(stack1)
    + "</li>\n	<li><strong>State:</strong> ";
  if (stack1 = helpers.state) { stack1 = stack1.call(depth0, {hash:{},data:data}); }
  else { stack1 = depth0.state; stack1 = typeof stack1 === functionType ? stack1.apply(depth0) : stack1; }
  buffer += escapeExpression(stack1)
    + "</li>\n	<li title=\"Started at ";
  if (stack1 = helpers.formatted_start_time) { stack1 = stack1.call(depth0, {hash:{},data:data}); }
  else { stack1 = depth0.formatted_start_time; stack1 = typeof stack1 === functionType ? stack1.apply(depth0) : stack1; }
  buffer += escapeExpression(stack1)
    + "\"><strong>Uptime:</strong> ";
  if (stack1 = helpers.uptime_string) { stack1 = stack1.call(depth0, {hash:{},data:data}); }
  else { stack1 = depth0.uptime_string; stack1 = typeof stack1 === functionType ? stack1.apply(depth0) : stack1; }
  buffer += escapeExpression(stack1)
    + "</li>\n	<li title=\"";
  if (stack1 = helpers.formatted_last_heard) { stack1 = stack1.call(depth0, {hash:{},data:data}); }
  else { stack1 = depth0.formatted_last_heard; stack1 = typeof stack1 === functionType ? stack1.apply(depth0) : stack1; }
  buffer += escapeExpression(stack1)
    + "\"><strong>Last report:</strong> ";
  if (stack1 = helpers.updated_age) { stack1 = stack1.call(depth0, {hash:{},data:data}); }
  else { stack1 = depth0.updated_age; stack1 = typeof stack1 === functionType ? stack1.apply(depth0) : stack1; }
  buffer += escapeExpression(stack1)
    + " seconds ago</li>\n	<li><strong>Score:</strong> ";
  if (stack1 = helpers.formatted_score) { stack1 = stack1.call(depth0, {hash:{},data:data}); }
  else { stack1 = depth0.formatted_score; stack1 = typeof stack1 === functionType ? stack1.apply(depth0) : stack1; }
  buffer += escapeExpression(stack1)
    + "</li>\n</ul>\n\n<h2 class=\"node-instances\">Instances</h2>\n<table class=\"table table-bordered node-instances\">\n	<tr class=\"node-table-header\">\n		<th>ID</th>\n		<th>Application</th>\n		<th>Version</th>\n		<th>State</th>\n		<th></th>\n	</tr>\n</table>\n\n<hr>\n\n";
  stack1 = helpers['if'].call(depth0, depth0.runtimes, {hash:{},inverse:self.noop,fn:self.program(7, program7, data),data:data});
  if(stack1 || stack1 === 0) { buffer += stack1; }
  buffer += "\n\n<table class=\"table table-bordered\">\n	<tr>\n		<th>Tags</th>\n		<th>Stats</th>\n	</tr>\n	<tr>\n		<td>\n			<pre>";
  if (stack1 = helpers.formatted_tags) { stack1 = stack1.call(depth0, {hash:{},data:data}); }
  else { stack1 = depth0.formatted_tags; stack1 = typeof stack1 === functionType ? stack1.apply(depth0) : stack1; }
  buffer += escapeExpression(stack1)
    + "</pre>\n		</td>\n		<td>\n			<pre>";
  if (stack1 = helpers.formatted_stats) { stack1 = stack1.call(depth0, {hash:{},data:data}); }
  else { stack1 = depth0.formatted_stats; stack1 = typeof stack1 === functionType ? stack1.apply(depth0) : stack1; }
  buffer += escapeExpression(stack1)
    + "</pre>\n		</td>\n	</tr>\n</table>\n\n<table class=\"table table-bordered jobs\">\n	<tr>\n		<th>\n			Jobs\n			<div class=\"all-jobs-button\">\n				<a class=\"btn btn-mini\" href=\"/job/list/node/";
  if (stack1 = helpers.id) { stack1 = stack1.call(depth0, {hash:{},data:data}); }
  else { stack1 = depth0.id; stack1 = typeof stack1 === functionType ? stack1.apply(depth0) : stack1; }
  buffer += escapeExpression(stack1)
    + "\">View All</a>\n			</div>\n		</th>\n	</tr>\n	<tr>\n		<td>\n			<div class=\"well job-overview\"></div>\n		</td>\n	</tr>\n</table>";
  return buffer;
  });
})();(function() {
  var template = Handlebars.template, templates = Handlebars.templates = Handlebars.templates || {};
templates['node_list'] = template(function (Handlebars,depth0,helpers,partials,data) {
  this.compilerInfo = [2,'>= 1.0.0-rc.3'];
helpers = helpers || Handlebars.helpers; data = data || {};
  var buffer = "", stack1, functionType="function", escapeExpression=this.escapeExpression, self=this, helperMissing=helpers.helperMissing;

function program1(depth0,data) {
  
  var buffer = "", stack1, stack2, options;
  buffer += "\n		<tr>\n			<td>\n				";
  stack1 = helpers['if'].call(depth0, depth0.can_delete, {hash:{},inverse:self.noop,fn:self.program(2, program2, data),data:data});
  if(stack1 || stack1 === 0) { buffer += stack1; }
  buffer += "\n\n				";
  options = {hash:{},inverse:self.noop,fn:self.program(5, program5, data),data:data};
  stack2 = ((stack1 = helpers.ifPermission),stack1 ? stack1.call(depth0, "NODE_DETAIL_VIEW", options) : helperMissing.call(depth0, "ifPermission", "NODE_DETAIL_VIEW", options));
  if(stack2 || stack2 === 0) { buffer += stack2; }
  buffer += "\n					<span style=\"font-weight:bold\" title=\"UUID: ";
  if (stack2 = helpers.uuid) { stack2 = stack2.call(depth0, {hash:{},data:data}); }
  else { stack2 = depth0.uuid; stack2 = typeof stack2 === functionType ? stack2.apply(depth0) : stack2; }
  buffer += escapeExpression(stack2)
    + "\">";
  if (stack2 = helpers.name) { stack2 = stack2.call(depth0, {hash:{},data:data}); }
  else { stack2 = depth0.name; stack2 = typeof stack2 === functionType ? stack2.apply(depth0) : stack2; }
  buffer += escapeExpression(stack2)
    + "</span>\n				";
  options = {hash:{},inverse:self.noop,fn:self.program(7, program7, data),data:data};
  stack2 = ((stack1 = helpers.ifPermission),stack1 ? stack1.call(depth0, "NODE_DETAIL_VIEW", options) : helperMissing.call(depth0, "ifPermission", "NODE_DETAIL_VIEW", options));
  if(stack2 || stack2 === 0) { buffer += stack2; }
  buffer += "\n				<span class=\"badge "
    + escapeExpression(((stack1 = ((stack1 = depth0.state_class),stack1 == null || stack1 === false ? stack1 : stack1.badge)),typeof stack1 === functionType ? stack1.apply(depth0) : stack1))
    + "\" title=\"State: ";
  if (stack2 = helpers.state) { stack2 = stack2.call(depth0, {hash:{},data:data}); }
  else { stack2 = depth0.state; stack2 = typeof stack2 === functionType ? stack2.apply(depth0) : stack2; }
  buffer += escapeExpression(stack2)
    + "\"><i class=\""
    + escapeExpression(((stack1 = ((stack1 = depth0.state_class),stack1 == null || stack1 === false ? stack1 : stack1.icon)),typeof stack1 === functionType ? stack1.apply(depth0) : stack1))
    + " icon-white\"></i></span><br>\n				";
  if (stack2 = helpers.route) { stack2 = stack2.call(depth0, {hash:{},data:data}); }
  else { stack2 = depth0.route; stack2 = typeof stack2 === functionType ? stack2.apply(depth0) : stack2; }
  buffer += escapeExpression(stack2)
    + ":";
  if (stack2 = helpers.apiport) { stack2 = stack2.call(depth0, {hash:{},data:data}); }
  else { stack2 = depth0.apiport; stack2 = typeof stack2 === functionType ? stack2.apply(depth0) : stack2; }
  buffer += escapeExpression(stack2)
    + "\n			</td>\n		</tr>\n	";
  return buffer;
  }
function program2(depth0,data) {
  
  var stack1, stack2, options;
  options = {hash:{},inverse:self.noop,fn:self.program(3, program3, data),data:data};
  stack2 = ((stack1 = helpers.ifPermission),stack1 ? stack1.call(depth0, "SYSTEM_ADMINISTRATION", options) : helperMissing.call(depth0, "ifPermission", "SYSTEM_ADMINISTRATION", options));
  if(stack2 || stack2 === 0) { return stack2; }
  else { return ''; }
  }
function program3(depth0,data) {
  
  var buffer = "", stack1;
  buffer += "\n					<a class=\"btn btn-small btn-danger job-action-button node-delete-button\" data-node-name=\"";
  if (stack1 = helpers.name) { stack1 = stack1.call(depth0, {hash:{},data:data}); }
  else { stack1 = depth0.name; stack1 = typeof stack1 === functionType ? stack1.apply(depth0) : stack1; }
  buffer += escapeExpression(stack1)
    + "\" data-node-id=\"";
  if (stack1 = helpers.id) { stack1 = stack1.call(depth0, {hash:{},data:data}); }
  else { stack1 = depth0.id; stack1 = typeof stack1 === functionType ? stack1.apply(depth0) : stack1; }
  buffer += escapeExpression(stack1)
    + "\">Delete</a>\n				";
  return buffer;
  }

function program5(depth0,data) {
  
  var buffer = "", stack1;
  buffer += "<a href=\"/node/";
  if (stack1 = helpers.id) { stack1 = stack1.call(depth0, {hash:{},data:data}); }
  else { stack1 = depth0.id; stack1 = typeof stack1 === functionType ? stack1.apply(depth0) : stack1; }
  buffer += escapeExpression(stack1)
    + "\">";
  return buffer;
  }

function program7(depth0,data) {
  
  
  return "</a>";
  }

  buffer += "<h1>Nodes</h1>\n\n<table class=\"table table-bordered node-list-category\">\n	<tr>\n		<th><i class=\"icon-calendar\"></i> Pacemakers</th>\n	</tr>\n	";
  stack1 = helpers.each.call(depth0, depth0.pacemakers, {hash:{},inverse:self.noop,fn:self.program(1, program1, data),data:data});
  if(stack1 || stack1 === 0) { buffer += stack1; }
  buffer += "\n</table>\n\n<table class=\"table table-bordered node-list-category\">\n	<tr>\n		<th><i class=\"icon-heart\"></i> Hearts</th>\n	</tr>\n	";
  stack1 = helpers.each.call(depth0, depth0.hearts, {hash:{},inverse:self.noop,fn:self.program(1, program1, data),data:data});
  if(stack1 || stack1 === 0) { buffer += stack1; }
  buffer += "\n</table>\n\n<table class=\"table table-bordered node-list-category\">\n	<tr>\n		<th><i class=\"icon-random\"></i> Routers</th>\n	</tr>\n	";
  stack1 = helpers.each.call(depth0, depth0.routers, {hash:{},inverse:self.noop,fn:self.program(1, program1, data),data:data});
  if(stack1 || stack1 === 0) { buffer += stack1; }
  buffer += "\n</table>\n";
  return buffer;
  });
})();(function() {
  var template = Handlebars.template, templates = Handlebars.templates = Handlebars.templates || {};
templates['version_manifest'] = template(function (Handlebars,depth0,helpers,partials,data) {
  this.compilerInfo = [2,'>= 1.0.0-rc.3'];
helpers = helpers || Handlebars.helpers; data = data || {};
  var buffer = "", stack1, functionType="function", escapeExpression=this.escapeExpression;


  buffer += "<pre>";
  if (stack1 = helpers.manifest) { stack1 = stack1.call(depth0, {hash:{},data:data}); }
  else { stack1 = depth0.manifest; stack1 = typeof stack1 === functionType ? stack1.apply(depth0) : stack1; }
  buffer += escapeExpression(stack1)
    + "</pre>";
  return buffer;
  });
})();(function() {
  var template = Handlebars.template, templates = Handlebars.templates = Handlebars.templates || {};
templates['version_instance_types'] = template(function (Handlebars,depth0,helpers,partials,data) {
  this.compilerInfo = [2,'>= 1.0.0-rc.3'];
helpers = helpers || Handlebars.helpers; data = data || {};
  var buffer = "", stack1, stack2, options, functionType="function", escapeExpression=this.escapeExpression, self=this, helperMissing=helpers.helperMissing;

function program1(depth0,data) {
  
  
  return "\n				<a class=\"btn btn-mini editable-button\"><i class=\"icon-edit\"></i></a>\n			";
  }

function program3(depth0,data) {
  
  
  return "\n			Exclusive\n		";
  }

function program5(depth0,data) {
  
  
  return "\n			Not exclusive\n		";
  }

function program7(depth0,data) {
  
  
  return "\n		Instance is standalone\n	";
  }

function program9(depth0,data,depth1) {
  
  var buffer = "", stack1, stack2;
  buffer += "\n		Hostnames:\n		<ul>\n			";
  stack2 = helpers.each.call(depth0, ((stack1 = depth0.instance_type),stack1 == null || stack1 === false ? stack1 : stack1.hostnames), {hash:{},inverse:self.noop,fn:self.programWithDepth(program10, data, depth0, depth1),data:data});
  if(stack2 || stack2 === 0) { buffer += stack2; }
  buffer += "\n			<li><a href=\"http://"
    + escapeExpression(((stack1 = ((stack1 = depth0.instance_type),stack1 == null || stack1 === false ? stack1 : stack1.version_url)),typeof stack1 === functionType ? stack1.apply(depth0) : stack1));
  if (stack2 = helpers.frontend_domain_postfix) { stack2 = stack2.call(depth0, {hash:{},data:data}); }
  else { stack2 = depth0.frontend_domain_postfix; stack2 = typeof stack2 === functionType ? stack2.apply(depth0) : stack2; }
  buffer += escapeExpression(stack2)
    + "\" target=\"_blank\">\n				"
    + escapeExpression(((stack1 = ((stack1 = depth0.instance_type),stack1 == null || stack1 === false ? stack1 : stack1.version_url)),typeof stack1 === functionType ? stack1.apply(depth0) : stack1))
    + "\n			</a></li>\n		</ul>\n	";
  return buffer;
  }
function program10(depth0,data,depth1,depth2) {
  
  var buffer = "", stack1;
  buffer += "\n				";
  stack1 = helpers['if'].call(depth0, depth2.version_is_current, {hash:{},inverse:self.program(13, program13, data),fn:self.programWithDepth(program11, data, depth1),data:data});
  if(stack1 || stack1 === 0) { buffer += stack1; }
  buffer += "\n			";
  return buffer;
  }
function program11(depth0,data,depth2) {
  
  var buffer = "", stack1;
  buffer += "\n					<li><a href=\"http://"
    + escapeExpression((typeof depth0 === functionType ? depth0.apply(depth0) : depth0))
    + escapeExpression(((stack1 = depth2.frontend_domain_postfix),typeof stack1 === functionType ? stack1.apply(depth0) : stack1))
    + "/\" target=\"_blank\">\n						"
    + escapeExpression((typeof depth0 === functionType ? depth0.apply(depth0) : depth0))
    + "\n					</a></li>\n				";
  return buffer;
  }

function program13(depth0,data) {
  
  var buffer = "";
  buffer += "\n					<li><i class=\" icon-minus-sign\" title=\"Hostname is configured for this version, but version is not current\"></i> "
    + escapeExpression((typeof depth0 === functionType ? depth0.apply(depth0) : depth0))
    + "</li>\n				";
  return buffer;
  }

function program15(depth0,data) {
  
  var buffer = "", stack1, stack2;
  buffer += "\n		<tr>\n			<td class=\"contains-uuid\">\n				<code class=\"uuid-shrink\" title=\"";
  if (stack1 = helpers.instance_id) { stack1 = stack1.call(depth0, {hash:{},data:data}); }
  else { stack1 = depth0.instance_id; stack1 = typeof stack1 === functionType ? stack1.apply(depth0) : stack1; }
  buffer += escapeExpression(stack1)
    + "\"></code>\n			</td>\n			<td>\n				<a href=\"/node/";
  if (stack1 = helpers.node_id) { stack1 = stack1.call(depth0, {hash:{},data:data}); }
  else { stack1 = depth0.node_id; stack1 = typeof stack1 === functionType ? stack1.apply(depth0) : stack1; }
  buffer += escapeExpression(stack1)
    + "\" class=\"version-instance-list-node\" data-node-id=\"";
  if (stack1 = helpers.node_id) { stack1 = stack1.call(depth0, {hash:{},data:data}); }
  else { stack1 = depth0.node_id; stack1 = typeof stack1 === functionType ? stack1.apply(depth0) : stack1; }
  buffer += escapeExpression(stack1)
    + "\">";
  if (stack1 = helpers.node_id) { stack1 = stack1.call(depth0, {hash:{},data:data}); }
  else { stack1 = depth0.node_id; stack1 = typeof stack1 === functionType ? stack1.apply(depth0) : stack1; }
  buffer += escapeExpression(stack1)
    + "</a>\n			</td>\n			<td>\n				";
  if (stack1 = helpers.port) { stack1 = stack1.call(depth0, {hash:{},data:data}); }
  else { stack1 = depth0.port; stack1 = typeof stack1 === functionType ? stack1.apply(depth0) : stack1; }
  buffer += escapeExpression(stack1)
    + "\n			</td>\n			<td title=\""
    + escapeExpression(((stack1 = ((stack1 = depth0.created_moment),stack1 == null || stack1 === false ? stack1 : stack1.format)),typeof stack1 === functionType ? stack1.apply(depth0) : stack1))
    + "\">\n				"
    + escapeExpression(((stack1 = ((stack1 = depth0.created_moment),stack1 == null || stack1 === false ? stack1 : stack1.fromNow)),typeof stack1 === functionType ? stack1.apply(depth0) : stack1))
    + "\n			</td>\n			<td>\n				<span class=\"instance-";
  if (stack2 = helpers.state) { stack2 = stack2.call(depth0, {hash:{},data:data}); }
  else { stack2 = depth0.state; stack2 = typeof stack2 === functionType ? stack2.apply(depth0) : stack2; }
  buffer += escapeExpression(stack2)
    + "\">";
  if (stack2 = helpers.state) { stack2 = stack2.call(depth0, {hash:{},data:data}); }
  else { stack2 = depth0.state; stack2 = typeof stack2 === functionType ? stack2.apply(depth0) : stack2; }
  buffer += escapeExpression(stack2)
    + "</span>\n			</td>\n			<td class=\"instance-log-button\">\n				<a href=\"#\" class=\"btn btn-mini toggle ";
  if (stack2 = helpers.instance_id) { stack2 = stack2.call(depth0, {hash:{},data:data}); }
  else { stack2 = depth0.instance_id; stack2 = typeof stack2 === functionType ? stack2.apply(depth0) : stack2; }
  buffer += escapeExpression(stack2)
    + "\"><i class=\"icon-list\"></i> View Log</a>\n			</td>\n		</tr>\n		<tr>\n			<td colspan=\"6\" class=\"instance-log-container ";
  if (stack2 = helpers.instance_id) { stack2 = stack2.call(depth0, {hash:{},data:data}); }
  else { stack2 = depth0.instance_id; stack2 = typeof stack2 === functionType ? stack2.apply(depth0) : stack2; }
  buffer += escapeExpression(stack2)
    + "\" data-instance=\"";
  if (stack2 = helpers.instance_id) { stack2 = stack2.call(depth0, {hash:{},data:data}); }
  else { stack2 = depth0.instance_id; stack2 = typeof stack2 === functionType ? stack2.apply(depth0) : stack2; }
  buffer += escapeExpression(stack2)
    + "\">\n			</td>\n		</tr>\n	";
  return buffer;
  }

  buffer += "<hr><h2>Instance type: "
    + escapeExpression(((stack1 = ((stack1 = depth0.instance_type),stack1 == null || stack1 === false ? stack1 : stack1.name)),typeof stack1 === functionType ? stack1.apply(depth0) : stack1))
    + "</h2>\n<ul class=\"instance-type-column\">\n	<li>Runtime: "
    + escapeExpression(((stack1 = ((stack1 = depth0.instance_type),stack1 == null || stack1 === false ? stack1 : stack1.runtime_name)),typeof stack1 === functionType ? stack1.apply(depth0) : stack1))
    + "</li>\n	<li>\n		Quantity:\n		<span class=\"editable\" data-editable-type=\"instance-type-quantity\" data-value=\""
    + escapeExpression(((stack1 = ((stack1 = depth0.instance_type),stack1 == null || stack1 === false ? stack1 : stack1.quantity)),typeof stack1 === functionType ? stack1.apply(depth0) : stack1))
    + "\" data-endpoint=\"/instancetype/"
    + escapeExpression(((stack1 = ((stack1 = depth0.instance_type),stack1 == null || stack1 === false ? stack1 : stack1.id)),typeof stack1 === functionType ? stack1.apply(depth0) : stack1))
    + "/quantity\">\n			"
    + escapeExpression(((stack1 = ((stack1 = depth0.instance_type),stack1 == null || stack1 === false ? stack1 : stack1.quantity)),typeof stack1 === functionType ? stack1.apply(depth0) : stack1))
    + "\n			";
  options = {hash:{},inverse:self.noop,fn:self.program(1, program1, data),data:data};
  stack2 = ((stack1 = helpers.ifPermission),stack1 ? stack1.call(depth0, "APPLICATION_CREATE", depth0.workspace_id, options) : helperMissing.call(depth0, "ifPermission", "APPLICATION_CREATE", depth0.workspace_id, options));
  if(stack2 || stack2 === 0) { buffer += stack2; }
  buffer += "\n		</span>\n	</li>\n	<li>\n		";
  stack2 = helpers['if'].call(depth0, ((stack1 = depth0.instance_type),stack1 == null || stack1 === false ? stack1 : stack1.exclusive), {hash:{},inverse:self.program(5, program5, data),fn:self.program(3, program3, data),data:data});
  if(stack2 || stack2 === 0) { buffer += stack2; }
  buffer += "\n	</li>\n</ul>\n<div class=\"instance-type-column\">\n	";
  stack2 = helpers['if'].call(depth0, ((stack1 = depth0.instance_type),stack1 == null || stack1 === false ? stack1 : stack1.standalone), {hash:{},inverse:self.programWithDepth(program9, data, depth0),fn:self.program(7, program7, data),data:data});
  if(stack2 || stack2 === 0) { buffer += stack2; }
  buffer += "\n</div>\n\n\n<table class=\"table table-striped table-bordered\">\n	<tr>\n		<th>ID</th>\n		<th>Node</th>\n		<th>Port</th>\n		<th>Created</th>\n		<th>State</th>\n		<th></th>\n	</tr>\n	";
  stack2 = helpers.each.call(depth0, depth0.instances, {hash:{},inverse:self.noop,fn:self.program(15, program15, data),data:data});
  if(stack2 || stack2 === 0) { buffer += stack2; }
  buffer += "\n</table>\n";
  return buffer;
  });
})();(function() {
  var template = Handlebars.template, templates = Handlebars.templates = Handlebars.templates || {};
templates['version_view'] = template(function (Handlebars,depth0,helpers,partials,data) {
  this.compilerInfo = [2,'>= 1.0.0-rc.3'];
helpers = helpers || Handlebars.helpers; data = data || {};
  var buffer = "", stack1, stack2, options, functionType="function", escapeExpression=this.escapeExpression, self=this, helperMissing=helpers.helperMissing;

function program1(depth0,data) {
  
  
  return "\n		<a href=\"#\" class=\"btn btn-success disabled\">\n			<i class=\"icon-star icon-white\"></i> Current\n		</a>\n	";
  }

function program3(depth0,data) {
  
  
  return "\n		<a href=\"#\" class=\"btn disabled\">\n			<i class=\"icon-minus\"></i> Not current\n		</a>\n	";
  }

function program5(depth0,data) {
  
  
  return "\n		<div class=\"btn-group btn-group-header\">\n			<a class=\"btn\" data-toggle=\"modal\" data-target=\"#app_manifest_modal\">View Manifest</a>\n		</div>\n	";
  }

function program7(depth0,data) {
  
  var buffer = "", stack1;
  buffer += "\n			<a class=\"btn btn-success job-action-button\" href=\"/version/"
    + escapeExpression(((stack1 = ((stack1 = depth0.version),stack1 == null || stack1 === false ? stack1 : stack1.id)),typeof stack1 === functionType ? stack1.apply(depth0) : stack1))
    + "/register\">Register</a>\n		";
  return buffer;
  }

function program9(depth0,data) {
  
  var buffer = "", stack1;
  buffer += "\n			<a class=\"btn btn-success job-action-button\" href=\"/version/"
    + escapeExpression(((stack1 = ((stack1 = depth0.version),stack1 == null || stack1 === false ? stack1 : stack1.id)),typeof stack1 === functionType ? stack1.apply(depth0) : stack1))
    + "/start\">Start</a>\n		";
  return buffer;
  }

function program11(depth0,data) {
  
  var buffer = "", stack1;
  buffer += "\n			<a class=\"btn btn-danger job-action-button\" href=\"/version/"
    + escapeExpression(((stack1 = ((stack1 = depth0.version),stack1 == null || stack1 === false ? stack1 : stack1.id)),typeof stack1 === functionType ? stack1.apply(depth0) : stack1))
    + "/stop\">Stop</a>\n		";
  return buffer;
  }

function program13(depth0,data) {
  
  var buffer = "", stack1;
  buffer += "\n			<a class=\"btn btn-warning job-action-button\" href=\"/version/"
    + escapeExpression(((stack1 = ((stack1 = depth0.version),stack1 == null || stack1 === false ? stack1 : stack1.id)),typeof stack1 === functionType ? stack1.apply(depth0) : stack1))
    + "/deregister\">De Register</a>\n		";
  return buffer;
  }

function program15(depth0,data) {
  
  var buffer = "", stack1;
  buffer += "\n			<a class=\"btn btn-primary job-action-button\" href=\"/version/"
    + escapeExpression(((stack1 = ((stack1 = depth0.version),stack1 == null || stack1 === false ? stack1 : stack1.id)),typeof stack1 === functionType ? stack1.apply(depth0) : stack1))
    + "/setcurrent\">Make Current</a>\n		";
  return buffer;
  }

function program17(depth0,data) {
  
  var buffer = "", stack1;
  buffer += "\n			<a class=\"btn btn-danger job-action-button\" href=\"/version/"
    + escapeExpression(((stack1 = ((stack1 = depth0.version),stack1 == null || stack1 === false ? stack1 : stack1.id)),typeof stack1 === functionType ? stack1.apply(depth0) : stack1))
    + "/delete\">Delete</a>\n		";
  return buffer;
  }

function program19(depth0,data) {
  
  var buffer = "", stack1;
  buffer += "\n		<li><b>Original source location:</b> "
    + escapeExpression(((stack1 = ((stack1 = ((stack1 = depth0.version),stack1 == null || stack1 === false ? stack1 : stack1.scm_parameters)),stack1 == null || stack1 === false ? stack1 : stack1.formatted_location)),typeof stack1 === functionType ? stack1.apply(depth0) : stack1))
    + "</li>\n	";
  return buffer;
  }

function program21(depth0,data) {
  
  var buffer = "", stack1, stack2;
  buffer += "\n		";
  stack2 = helpers['if'].call(depth0, ((stack1 = ((stack1 = depth0.version),stack1 == null || stack1 === false ? stack1 : stack1.scm_parameters)),stack1 == null || stack1 === false ? stack1 : stack1.location), {hash:{},inverse:self.noop,fn:self.program(22, program22, data),data:data});
  if(stack2 || stack2 === 0) { buffer += stack2; }
  buffer += "\n	";
  return buffer;
  }
function program22(depth0,data) {
  
  var buffer = "", stack1;
  buffer += "\n			<li><b>Original source location:</b> "
    + escapeExpression(((stack1 = ((stack1 = ((stack1 = depth0.version),stack1 == null || stack1 === false ? stack1 : stack1.scm_parameters)),stack1 == null || stack1 === false ? stack1 : stack1.location)),typeof stack1 === functionType ? stack1.apply(depth0) : stack1))
    + "</li>\n		";
  return buffer;
  }

function program24(depth0,data) {
  
  var buffer = "", stack1;
  buffer += "\n		<li><b>Package type:</b> "
    + escapeExpression(((stack1 = ((stack1 = depth0.version),stack1 == null || stack1 === false ? stack1 : stack1.source_package_type)),typeof stack1 === functionType ? stack1.apply(depth0) : stack1))
    + "</li>\n	";
  return buffer;
  }

  buffer += "<ul class=\"breadcrumb\"></ul>\n\n<div class=\"router-stats well well-small\" data-name=\"version\" data-inputid=\""
    + escapeExpression(((stack1 = ((stack1 = depth0.version),stack1 == null || stack1 === false ? stack1 : stack1.id)),typeof stack1 === functionType ? stack1.apply(depth0) : stack1))
    + "\">Loading...</div>\n\n<h1>\n	Version "
    + escapeExpression(((stack1 = ((stack1 = depth0.version),stack1 == null || stack1 === false ? stack1 : stack1.version)),typeof stack1 === functionType ? stack1.apply(depth0) : stack1))
    + "\n	";
  stack2 = helpers['if'].call(depth0, ((stack1 = depth0.version),stack1 == null || stack1 === false ? stack1 : stack1.is_current), {hash:{},inverse:self.program(3, program3, data),fn:self.program(1, program1, data),data:data});
  if(stack2 || stack2 === 0) { buffer += stack2; }
  buffer += "\n</h1>\n\n<div class=\"btn-toolbar\">\n	<div class=\"btn-group btn-group-header\">\n		<a class=\"btn\" href=\"/job/list/version/"
    + escapeExpression(((stack1 = ((stack1 = depth0.version),stack1 == null || stack1 === false ? stack1 : stack1.id)),typeof stack1 === functionType ? stack1.apply(depth0) : stack1))
    + "\">All Jobs</a>\n		<a class=\"btn\" href=\"/job/list/version/"
    + escapeExpression(((stack1 = ((stack1 = depth0.version),stack1 == null || stack1 === false ? stack1 : stack1.id)),typeof stack1 === functionType ? stack1.apply(depth0) : stack1))
    + "?sub=cron\">Crons</a>\n	</div>\n	";
  options = {hash:{},inverse:self.noop,fn:self.program(5, program5, data),data:data};
  stack2 = ((stack1 = helpers.ifPermission),stack1 ? stack1.call(depth0, "APPLICATION_VIEW_MANIFEST", depth0.workspace_id, options) : helperMissing.call(depth0, "ifPermission", "APPLICATION_VIEW_MANIFEST", depth0.workspace_id, options));
  if(stack2 || stack2 === 0) { buffer += stack2; }
  buffer += "\n	<div class=\"btn-group btn-group-header\">\n		"
    + "\n		";
  stack2 = helpers['if'].call(depth0, ((stack1 = ((stack1 = depth0.version),stack1 == null || stack1 === false ? stack1 : stack1.buttons_to_show)),stack1 == null || stack1 === false ? stack1 : stack1.register), {hash:{},inverse:self.noop,fn:self.program(7, program7, data),data:data});
  if(stack2 || stack2 === 0) { buffer += stack2; }
  buffer += "\n		";
  stack2 = helpers['if'].call(depth0, ((stack1 = ((stack1 = depth0.version),stack1 == null || stack1 === false ? stack1 : stack1.buttons_to_show)),stack1 == null || stack1 === false ? stack1 : stack1.start), {hash:{},inverse:self.noop,fn:self.program(9, program9, data),data:data});
  if(stack2 || stack2 === 0) { buffer += stack2; }
  buffer += "\n		";
  stack2 = helpers['if'].call(depth0, ((stack1 = ((stack1 = depth0.version),stack1 == null || stack1 === false ? stack1 : stack1.buttons_to_show)),stack1 == null || stack1 === false ? stack1 : stack1.stop), {hash:{},inverse:self.noop,fn:self.program(11, program11, data),data:data});
  if(stack2 || stack2 === 0) { buffer += stack2; }
  buffer += "\n		";
  stack2 = helpers['if'].call(depth0, ((stack1 = ((stack1 = depth0.version),stack1 == null || stack1 === false ? stack1 : stack1.buttons_to_show)),stack1 == null || stack1 === false ? stack1 : stack1.deregister), {hash:{},inverse:self.noop,fn:self.program(13, program13, data),data:data});
  if(stack2 || stack2 === 0) { buffer += stack2; }
  buffer += "\n		";
  stack2 = helpers['if'].call(depth0, ((stack1 = ((stack1 = depth0.version),stack1 == null || stack1 === false ? stack1 : stack1.buttons_to_show)),stack1 == null || stack1 === false ? stack1 : stack1.makecurrent), {hash:{},inverse:self.noop,fn:self.program(15, program15, data),data:data});
  if(stack2 || stack2 === 0) { buffer += stack2; }
  buffer += "\n		";
  stack2 = helpers['if'].call(depth0, ((stack1 = ((stack1 = depth0.version),stack1 == null || stack1 === false ? stack1 : stack1.buttons_to_show)),stack1 == null || stack1 === false ? stack1 : stack1['delete']), {hash:{},inverse:self.noop,fn:self.program(17, program17, data),data:data});
  if(stack2 || stack2 === 0) { buffer += stack2; }
  buffer += "\n	</div>\n</div>\n\n<ul>\n	<li><b>State:</b> "
    + escapeExpression(((stack1 = ((stack1 = depth0.version),stack1 == null || stack1 === false ? stack1 : stack1.state)),typeof stack1 === functionType ? stack1.apply(depth0) : stack1))
    + "</li>\n	<li><b>Health:</b> "
    + escapeExpression(((stack1 = ((stack1 = ((stack1 = depth0.version),stack1 == null || stack1 === false ? stack1 : stack1.health)),stack1 == null || stack1 === false ? stack1 : stack1.overall)),typeof stack1 === functionType ? stack1.apply(depth0) : stack1))
    + " ";
  stack2 = ((stack1 = ((stack1 = depth0.version),stack1 == null || stack1 === false ? stack1 : stack1.health_string)),typeof stack1 === functionType ? stack1.apply(depth0) : stack1);
  if(stack2 || stack2 === 0) { buffer += stack2; }
  buffer += "</li>\n	<li><b>SCM:</b> "
    + escapeExpression(((stack1 = ((stack1 = depth0.version),stack1 == null || stack1 === false ? stack1 : stack1.scm_name)),typeof stack1 === functionType ? stack1.apply(depth0) : stack1))
    + "</li>\n	";
  stack2 = helpers['if'].call(depth0, ((stack1 = ((stack1 = depth0.version),stack1 == null || stack1 === false ? stack1 : stack1.scm_parameters)),stack1 == null || stack1 === false ? stack1 : stack1.formatted_location), {hash:{},inverse:self.program(21, program21, data),fn:self.program(19, program19, data),data:data});
  if(stack2 || stack2 === 0) { buffer += stack2; }
  buffer += "\n	";
  stack2 = helpers['if'].call(depth0, ((stack1 = depth0.version),stack1 == null || stack1 === false ? stack1 : stack1.using_dev_directory_plugin), {hash:{},inverse:self.noop,fn:self.program(24, program24, data),data:data});
  if(stack2 || stack2 === 0) { buffer += stack2; }
  buffer += "\n</ul>\n\n<div id=\"app_manifest_modal\" class=\"modal hide fade\" tabindex=\"-1\" role=\"dialog\" aria-labelledby=\"Application Manifest\" aria-hidden=\"true\">\n  <div class=\"modal-header\">\n    <button type=\"button\" class=\"close\" data-dismiss=\"modal\" aria-hidden=\"true\">×</button>\n    <h3>Application Manifest - Version "
    + escapeExpression(((stack1 = ((stack1 = depth0.version),stack1 == null || stack1 === false ? stack1 : stack1.version)),typeof stack1 === functionType ? stack1.apply(depth0) : stack1))
    + "</h3>\n  </div>\n  <div class=\"modal-body\">\n    <p>Loading ...</p>\n  </div>\n  <div class=\"modal-footer\">\n    <button class=\"btn\" data-dismiss=\"modal\" aria-hidden=\"true\">Close</button>\n  </div>\n</div>\n";
  return buffer;
  });
})();(function() {
  var template = Handlebars.template, templates = Handlebars.templates = Handlebars.templates || {};
templates['application_versions'] = template(function (Handlebars,depth0,helpers,partials,data) {
  this.compilerInfo = [2,'>= 1.0.0-rc.3'];
helpers = helpers || Handlebars.helpers; data = data || {};
  var buffer = "", stack1, stack2, functionType="function", escapeExpression=this.escapeExpression, self=this;

function program1(depth0,data) {
  
  
  return "\n		<div class=\"btn-group btn-group-header\">\n			<a class=\"btn btn-danger\" data-toggle=\"modal\" data-target=\"#app_delete_modal\"><i class=\"icon-trash icon-white\"></i> Delete Application</a>\n		</div>\n	";
  }

function program3(depth0,data) {
  
  
  return "\n<table class=\"table table-striped table-bordered current_version\">\n		<tr>\n			<th>Current version</th>\n			<th>State</th>\n			<th>Health</th>\n			<th>Instances</th>\n			<th>Actions</th>\n		</tr>\n</table>\n";
  }

  buffer += "<ul class=\"breadcrumb\"></ul>\n\n<div class=\"router-stats well well-small\" data-name=\"application\" data-inputid=\""
    + escapeExpression(((stack1 = ((stack1 = depth0.application),stack1 == null || stack1 === false ? stack1 : stack1.id)),typeof stack1 === functionType ? stack1.apply(depth0) : stack1))
    + "\">Loading...</div>\n\n<h1>Application: "
    + escapeExpression(((stack1 = ((stack1 = depth0.application),stack1 == null || stack1 === false ? stack1 : stack1.name)),typeof stack1 === functionType ? stack1.apply(depth0) : stack1))
    + "</h1>\n\n<div class=\"btn-toolbar\">\n	<div class=\"btn-group btn-group-header\">\n		<a class=\"btn\" href=\"/application/"
    + escapeExpression(((stack1 = ((stack1 = depth0.application),stack1 == null || stack1 === false ? stack1 : stack1.id)),typeof stack1 === functionType ? stack1.apply(depth0) : stack1))
    + "/newversion\"><i class=\"icon-plus\"></i> Create new version</a>\n	</div>\n	<div class=\"btn-group btn-group-header\">\n		<a class=\"btn\" href=\"/job/list/application/"
    + escapeExpression(((stack1 = ((stack1 = depth0.application),stack1 == null || stack1 === false ? stack1 : stack1.id)),typeof stack1 === functionType ? stack1.apply(depth0) : stack1))
    + "\">All Jobs</a>\n		<a class=\"btn\" href=\"/application/"
    + escapeExpression(((stack1 = ((stack1 = depth0.application),stack1 == null || stack1 === false ? stack1 : stack1.id)),typeof stack1 === functionType ? stack1.apply(depth0) : stack1))
    + "/services\">Services</a>\n		<a class=\"btn\" href=\"/job/list/application/"
    + escapeExpression(((stack1 = ((stack1 = depth0.application),stack1 == null || stack1 === false ? stack1 : stack1.id)),typeof stack1 === functionType ? stack1.apply(depth0) : stack1))
    + "?sub=cron\">Crons</a>\n	</div>\n	";
  stack2 = helpers['if'].call(depth0, ((stack1 = depth0.application),stack1 == null || stack1 === false ? stack1 : stack1.can_delete), {hash:{},inverse:self.noop,fn:self.program(1, program1, data),data:data});
  if(stack2 || stack2 === 0) { buffer += stack2; }
  buffer += "\n</div>\n\n<div id=\"app_delete_modal\" class=\"modal hide fade\" tabindex=\"-1\" role=\"dialog\" aria-labelledby=\"Delete Application\" aria-hidden=\"true\">\n  <div class=\"modal-header\">\n    <button type=\"button\" class=\"close\" data-dismiss=\"modal\" aria-hidden=\"true\">×</button>\n    <h3>Delete Application</h3>\n  </div>\n  <div class=\"modal-body\">\n	<p>Are you sure you want to delete "
    + escapeExpression(((stack1 = ((stack1 = depth0.application),stack1 == null || stack1 === false ? stack1 : stack1.name)),typeof stack1 === functionType ? stack1.apply(depth0) : stack1))
    + "?</p>\n	<p>This action cannot be undone.</p>\n  </div>\n  <div class=\"modal-footer\">\n    <button class=\"btn\" data-dismiss=\"modal\" aria-hidden=\"true\">Cancel</button>\n		<form method=\"POST\" action=\"/application/"
    + escapeExpression(((stack1 = ((stack1 = depth0.application),stack1 == null || stack1 === false ? stack1 : stack1.id)),typeof stack1 === functionType ? stack1.apply(depth0) : stack1))
    + "/delete\" style=\"display: inline;\">\n			<input type=\"submit\" class=\"btn btn-primary btn-danger\" value=\"Delete Application\" />\n		</form>\n  </div>\n</div>\n\n";
  stack2 = helpers['if'].call(depth0, depth0.current_version, {hash:{},inverse:self.noop,fn:self.program(3, program3, data),data:data});
  if(stack2 || stack2 === 0) { buffer += stack2; }
  buffer += "\n\n<table class=\"table table-striped table-bordered all_versions\">\n	<tr>\n		<th>Number</th>\n		<th>State</th>\n		<th>Health</th>\n		<th>Instances</th>\n		<th>Actions</th>\n	</tr>\n</table>\n";
  return buffer;
  });
})();(function() {
  var template = Handlebars.template, templates = Handlebars.templates = Handlebars.templates || {};
templates['application_version_row'] = template(function (Handlebars,depth0,helpers,partials,data) {
  this.compilerInfo = [2,'>= 1.0.0-rc.3'];
helpers = helpers || Handlebars.helpers; data = data || {};
  var buffer = "", stack1, stack2, functionType="function", escapeExpression=this.escapeExpression, self=this;

function program1(depth0,data) {
  
  
  return "<i class=\"icon-star\" title=\"Version is current\"></i>";
  }

function program3(depth0,data) {
  
  var buffer = "", stack1;
  buffer += "\n				<a class=\"btn btn-mini btn-success job-action-button\" data-version-id=\"";
  if (stack1 = helpers.id) { stack1 = stack1.call(depth0, {hash:{},data:data}); }
  else { stack1 = depth0.id; stack1 = typeof stack1 === functionType ? stack1.apply(depth0) : stack1; }
  buffer += escapeExpression(stack1)
    + "\" href=\"/version/";
  if (stack1 = helpers.id) { stack1 = stack1.call(depth0, {hash:{},data:data}); }
  else { stack1 = depth0.id; stack1 = typeof stack1 === functionType ? stack1.apply(depth0) : stack1; }
  buffer += escapeExpression(stack1)
    + "/register\">Register</a>\n			";
  return buffer;
  }

function program5(depth0,data) {
  
  var buffer = "", stack1;
  buffer += "\n				<a class=\"btn btn-mini btn-success job-action-button\" data-version-id=\"";
  if (stack1 = helpers.id) { stack1 = stack1.call(depth0, {hash:{},data:data}); }
  else { stack1 = depth0.id; stack1 = typeof stack1 === functionType ? stack1.apply(depth0) : stack1; }
  buffer += escapeExpression(stack1)
    + "\" href=\"/version/";
  if (stack1 = helpers.id) { stack1 = stack1.call(depth0, {hash:{},data:data}); }
  else { stack1 = depth0.id; stack1 = typeof stack1 === functionType ? stack1.apply(depth0) : stack1; }
  buffer += escapeExpression(stack1)
    + "/start\">Start</a>\n			";
  return buffer;
  }

function program7(depth0,data) {
  
  var buffer = "", stack1;
  buffer += "\n				<a class=\"btn btn-mini btn-danger job-action-button\" data-version-id=\"";
  if (stack1 = helpers.id) { stack1 = stack1.call(depth0, {hash:{},data:data}); }
  else { stack1 = depth0.id; stack1 = typeof stack1 === functionType ? stack1.apply(depth0) : stack1; }
  buffer += escapeExpression(stack1)
    + "\" href=\"/version/";
  if (stack1 = helpers.id) { stack1 = stack1.call(depth0, {hash:{},data:data}); }
  else { stack1 = depth0.id; stack1 = typeof stack1 === functionType ? stack1.apply(depth0) : stack1; }
  buffer += escapeExpression(stack1)
    + "/stop\">Stop</a>\n			";
  return buffer;
  }

function program9(depth0,data) {
  
  var buffer = "", stack1;
  buffer += "\n				<a class=\"btn btn-mini btn-warning job-action-button\" data-version-id=\"";
  if (stack1 = helpers.id) { stack1 = stack1.call(depth0, {hash:{},data:data}); }
  else { stack1 = depth0.id; stack1 = typeof stack1 === functionType ? stack1.apply(depth0) : stack1; }
  buffer += escapeExpression(stack1)
    + "\" href=\"/version/";
  if (stack1 = helpers.id) { stack1 = stack1.call(depth0, {hash:{},data:data}); }
  else { stack1 = depth0.id; stack1 = typeof stack1 === functionType ? stack1.apply(depth0) : stack1; }
  buffer += escapeExpression(stack1)
    + "/deregister\">De Register</a>\n			";
  return buffer;
  }

function program11(depth0,data) {
  
  var buffer = "", stack1;
  buffer += "\n				<a class=\"btn btn-mini btn-primary job-action-button\" data-version-id=\"";
  if (stack1 = helpers.id) { stack1 = stack1.call(depth0, {hash:{},data:data}); }
  else { stack1 = depth0.id; stack1 = typeof stack1 === functionType ? stack1.apply(depth0) : stack1; }
  buffer += escapeExpression(stack1)
    + "\" href=\"/version/";
  if (stack1 = helpers.id) { stack1 = stack1.call(depth0, {hash:{},data:data}); }
  else { stack1 = depth0.id; stack1 = typeof stack1 === functionType ? stack1.apply(depth0) : stack1; }
  buffer += escapeExpression(stack1)
    + "/setcurrent\">Make Current</a>\n			";
  return buffer;
  }

function program13(depth0,data) {
  
  var buffer = "", stack1;
  buffer += "\n				<a class=\"btn btn-mini btn-danger job-action-button\" data-version-id=\"";
  if (stack1 = helpers.id) { stack1 = stack1.call(depth0, {hash:{},data:data}); }
  else { stack1 = depth0.id; stack1 = typeof stack1 === functionType ? stack1.apply(depth0) : stack1; }
  buffer += escapeExpression(stack1)
    + "\" href=\"/version/";
  if (stack1 = helpers.id) { stack1 = stack1.call(depth0, {hash:{},data:data}); }
  else { stack1 = depth0.id; stack1 = typeof stack1 === functionType ? stack1.apply(depth0) : stack1; }
  buffer += escapeExpression(stack1)
    + "/delete\">Delete</a>\n			";
  return buffer;
  }

  buffer += "<tr>\n	<td>\n		<a href=\"/version/";
  if (stack1 = helpers.id) { stack1 = stack1.call(depth0, {hash:{},data:data}); }
  else { stack1 = depth0.id; stack1 = typeof stack1 === functionType ? stack1.apply(depth0) : stack1; }
  buffer += escapeExpression(stack1)
    + "\">Version ";
  if (stack1 = helpers.version) { stack1 = stack1.call(depth0, {hash:{},data:data}); }
  else { stack1 = depth0.version; stack1 = typeof stack1 === functionType ? stack1.apply(depth0) : stack1; }
  buffer += escapeExpression(stack1)
    + "</a>\n		";
  stack1 = helpers['if'].call(depth0, depth0.is_current, {hash:{},inverse:self.noop,fn:self.program(1, program1, data),data:data});
  if(stack1 || stack1 === 0) { buffer += stack1; }
  buffer += "\n	</td>\n	<td>\n		";
  if (stack1 = helpers.display_state) { stack1 = stack1.call(depth0, {hash:{},data:data}); }
  else { stack1 = depth0.display_state; stack1 = typeof stack1 === functionType ? stack1.apply(depth0) : stack1; }
  buffer += escapeExpression(stack1)
    + "\n	</td>\n	<td>\n		";
  if (stack1 = helpers.health_string) { stack1 = stack1.call(depth0, {hash:{},data:data}); }
  else { stack1 = depth0.health_string; stack1 = typeof stack1 === functionType ? stack1.apply(depth0) : stack1; }
  if(stack1 || stack1 === 0) { buffer += stack1; }
  buffer += "\n	</td>\n	<td class=\"version_instance_count\" data-version-id=\"";
  if (stack1 = helpers.id) { stack1 = stack1.call(depth0, {hash:{},data:data}); }
  else { stack1 = depth0.id; stack1 = typeof stack1 === functionType ? stack1.apply(depth0) : stack1; }
  buffer += escapeExpression(stack1)
    + "\">\n		<img src=\"/static/img/load-inline.gif\" alt=\"\">\n	</td>\n	<td>\n		<div class=\"table-button-box btn-group\">\n			"
    + "\n			";
  stack2 = helpers['if'].call(depth0, ((stack1 = depth0.buttons_to_show),stack1 == null || stack1 === false ? stack1 : stack1.register), {hash:{},inverse:self.noop,fn:self.program(3, program3, data),data:data});
  if(stack2 || stack2 === 0) { buffer += stack2; }
  buffer += "\n			";
  stack2 = helpers['if'].call(depth0, ((stack1 = depth0.buttons_to_show),stack1 == null || stack1 === false ? stack1 : stack1.start), {hash:{},inverse:self.noop,fn:self.program(5, program5, data),data:data});
  if(stack2 || stack2 === 0) { buffer += stack2; }
  buffer += "\n			";
  stack2 = helpers['if'].call(depth0, ((stack1 = depth0.buttons_to_show),stack1 == null || stack1 === false ? stack1 : stack1.stop), {hash:{},inverse:self.noop,fn:self.program(7, program7, data),data:data});
  if(stack2 || stack2 === 0) { buffer += stack2; }
  buffer += "\n			";
  stack2 = helpers['if'].call(depth0, ((stack1 = depth0.buttons_to_show),stack1 == null || stack1 === false ? stack1 : stack1.deregister), {hash:{},inverse:self.noop,fn:self.program(9, program9, data),data:data});
  if(stack2 || stack2 === 0) { buffer += stack2; }
  buffer += "\n			";
  stack2 = helpers['if'].call(depth0, ((stack1 = depth0.buttons_to_show),stack1 == null || stack1 === false ? stack1 : stack1.makecurrent), {hash:{},inverse:self.noop,fn:self.program(11, program11, data),data:data});
  if(stack2 || stack2 === 0) { buffer += stack2; }
  buffer += "\n			";
  stack2 = helpers['if'].call(depth0, ((stack1 = depth0.buttons_to_show),stack1 == null || stack1 === false ? stack1 : stack1['delete']), {hash:{},inverse:self.noop,fn:self.program(13, program13, data),data:data});
  if(stack2 || stack2 === 0) { buffer += stack2; }
  buffer += "\n		</div>\n	</td>\n</tr>\n";
  return buffer;
  });
})();(function() {
  var template = Handlebars.template, templates = Handlebars.templates = Handlebars.templates || {};
templates['application_services'] = template(function (Handlebars,depth0,helpers,partials,data) {
  this.compilerInfo = [2,'>= 1.0.0-rc.3'];
helpers = helpers || Handlebars.helpers; data = data || {};
  var buffer = "", stack1, stack2, functionType="function", escapeExpression=this.escapeExpression, self=this;

function program1(depth0,data) {
  
  var buffer = "", stack1;
  buffer += "\n		<tr>\n			<td>\n				";
  if (stack1 = helpers.name) { stack1 = stack1.call(depth0, {hash:{},data:data}); }
  else { stack1 = depth0.name; stack1 = typeof stack1 === functionType ? stack1.apply(depth0) : stack1; }
  buffer += escapeExpression(stack1)
    + "\n			</td>\n			<td>\n				";
  if (stack1 = helpers.provider) { stack1 = stack1.call(depth0, {hash:{},data:data}); }
  else { stack1 = depth0.provider; stack1 = typeof stack1 === functionType ? stack1.apply(depth0) : stack1; }
  buffer += escapeExpression(stack1)
    + "\n			</td>\n			<td>\n				";
  stack1 = helpers['if'].call(depth0, depth0.credentials_text, {hash:{},inverse:self.noop,fn:self.program(2, program2, data),data:data});
  if(stack1 || stack1 === 0) { buffer += stack1; }
  buffer += "\n			</td>\n			<td>\n				<ul>\n					";
  stack1 = helpers.each.call(depth0, depth0.application_versions, {hash:{},inverse:self.noop,fn:self.program(4, program4, data),data:data});
  if(stack1 || stack1 === 0) { buffer += stack1; }
  buffer += "\n				</ul>\n			</td>\n			<td>\n				<span class=\"service-";
  if (stack1 = helpers.state) { stack1 = stack1.call(depth0, {hash:{},data:data}); }
  else { stack1 = depth0.state; stack1 = typeof stack1 === functionType ? stack1.apply(depth0) : stack1; }
  buffer += escapeExpression(stack1)
    + "\">";
  if (stack1 = helpers.state) { stack1 = stack1.call(depth0, {hash:{},data:data}); }
  else { stack1 = depth0.state; stack1 = typeof stack1 === functionType ? stack1.apply(depth0) : stack1; }
  buffer += escapeExpression(stack1)
    + "</span>\n			</td>\n		</tr>\n	";
  return buffer;
  }
function program2(depth0,data) {
  
  var buffer = "", stack1;
  buffer += "\n					<pre>";
  if (stack1 = helpers.credentials_text) { stack1 = stack1.call(depth0, {hash:{},data:data}); }
  else { stack1 = depth0.credentials_text; stack1 = typeof stack1 === functionType ? stack1.apply(depth0) : stack1; }
  buffer += escapeExpression(stack1)
    + "</pre>\n				";
  return buffer;
  }

function program4(depth0,data) {
  
  var buffer = "", stack1;
  buffer += "\n						<li><a href=\"/version/";
  if (stack1 = helpers.id) { stack1 = stack1.call(depth0, {hash:{},data:data}); }
  else { stack1 = depth0.id; stack1 = typeof stack1 === functionType ? stack1.apply(depth0) : stack1; }
  buffer += escapeExpression(stack1)
    + "\">Version ";
  if (stack1 = helpers.version) { stack1 = stack1.call(depth0, {hash:{},data:data}); }
  else { stack1 = depth0.version; stack1 = typeof stack1 === functionType ? stack1.apply(depth0) : stack1; }
  buffer += escapeExpression(stack1)
    + "</a></li>\n					";
  return buffer;
  }

  buffer += "<ul class=\"breadcrumb\"></ul>\n\n<h1>Services: "
    + escapeExpression(((stack1 = ((stack1 = depth0.application),stack1 == null || stack1 === false ? stack1 : stack1.name)),typeof stack1 === functionType ? stack1.apply(depth0) : stack1))
    + "</h1>\n\n<table class=\"table table-striped table-bordered\">\n	<tr>\n		<th>Name</th>\n		<th>Provider</th>\n		<th>Credentials</th>\n		<th>Used By</th>\n		<th>State</th>\n	</tr>\n	";
  stack2 = helpers.each.call(depth0, depth0.services, {hash:{},inverse:self.noop,fn:self.program(1, program1, data),data:data});
  if(stack2 || stack2 === 0) { buffer += stack2; }
  buffer += "\n</table>\n";
  return buffer;
  });
})();(function() {
  var template = Handlebars.template, templates = Handlebars.templates = Handlebars.templates || {};
templates['node_menu'] = template(function (Handlebars,depth0,helpers,partials,data) {
  this.compilerInfo = [2,'>= 1.0.0-rc.3'];
helpers = helpers || Handlebars.helpers; data = data || {};
  var buffer = "", stack1, functionType="function", escapeExpression=this.escapeExpression, self=this, helperMissing=helpers.helperMissing;

function program1(depth0,data) {
  
  var buffer = "", stack1, stack2, options;
  buffer += "\n			<li class=\"node ";
  stack1 = helpers['if'].call(depth0, depth0.is_active, {hash:{},inverse:self.noop,fn:self.program(2, program2, data),data:data});
  if(stack1 || stack1 === 0) { buffer += stack1; }
  buffer += "\" data-node-id=\"";
  if (stack1 = helpers.id) { stack1 = stack1.call(depth0, {hash:{},data:data}); }
  else { stack1 = depth0.id; stack1 = typeof stack1 === functionType ? stack1.apply(depth0) : stack1; }
  buffer += escapeExpression(stack1)
    + "\">\n				";
  options = {hash:{},inverse:self.noop,fn:self.program(4, program4, data),data:data};
  stack2 = ((stack1 = helpers.ifPermission),stack1 ? stack1.call(depth0, "NODE_DETAIL_VIEW", options) : helperMissing.call(depth0, "ifPermission", "NODE_DETAIL_VIEW", options));
  if(stack2 || stack2 === 0) { buffer += stack2; }
  buffer += "\n					<span class=\"application-list-state\">\n						";
  stack2 = helpers['if'].call(depth0, depth0.pacemaker, {hash:{},inverse:self.noop,fn:self.program(6, program6, data),data:data});
  if(stack2 || stack2 === 0) { buffer += stack2; }
  buffer += "\n						";
  stack2 = helpers['if'].call(depth0, depth0.heart, {hash:{},inverse:self.noop,fn:self.program(9, program9, data),data:data});
  if(stack2 || stack2 === 0) { buffer += stack2; }
  buffer += "\n						";
  stack2 = helpers['if'].call(depth0, depth0.router, {hash:{},inverse:self.noop,fn:self.program(11, program11, data),data:data});
  if(stack2 || stack2 === 0) { buffer += stack2; }
  buffer += "\n						<span class=\"badge "
    + escapeExpression(((stack1 = ((stack1 = depth0.state_class),stack1 == null || stack1 === false ? stack1 : stack1.badge)),typeof stack1 === functionType ? stack1.apply(depth0) : stack1))
    + "\" title=\"State: ";
  if (stack2 = helpers.state) { stack2 = stack2.call(depth0, {hash:{},data:data}); }
  else { stack2 = depth0.state; stack2 = typeof stack2 === functionType ? stack2.apply(depth0) : stack2; }
  buffer += escapeExpression(stack2)
    + "\"><i class=\""
    + escapeExpression(((stack1 = ((stack1 = depth0.state_class),stack1 == null || stack1 === false ? stack1 : stack1.icon)),typeof stack1 === functionType ? stack1.apply(depth0) : stack1))
    + " icon-white\"></i></span>\n					</span>\n					<span class=\"application-list-name\">";
  if (stack2 = helpers.name) { stack2 = stack2.call(depth0, {hash:{},data:data}); }
  else { stack2 = depth0.name; stack2 = typeof stack2 === functionType ? stack2.apply(depth0) : stack2; }
  buffer += escapeExpression(stack2)
    + "</span>\n					<span class=\"application-list-details\">\n						Last heard: ";
  if (stack2 = helpers.updated_age) { stack2 = stack2.call(depth0, {hash:{},data:data}); }
  else { stack2 = depth0.updated_age; stack2 = typeof stack2 === functionType ? stack2.apply(depth0) : stack2; }
  buffer += escapeExpression(stack2)
    + "s &middot;\n						Score: ";
  if (stack2 = helpers.score) { stack2 = stack2.call(depth0, {hash:{},data:data}); }
  else { stack2 = depth0.score; stack2 = typeof stack2 === functionType ? stack2.apply(depth0) : stack2; }
  buffer += escapeExpression(stack2)
    + "\n					</span>\n				";
  options = {hash:{},inverse:self.noop,fn:self.program(13, program13, data),data:data};
  stack2 = ((stack1 = helpers.ifPermission),stack1 ? stack1.call(depth0, "NODE_DETAIL_VIEW", options) : helperMissing.call(depth0, "ifPermission", "NODE_DETAIL_VIEW", options));
  if(stack2 || stack2 === 0) { buffer += stack2; }
  buffer += "\n			</li>\n		";
  return buffer;
  }
function program2(depth0,data) {
  
  
  return "active";
  }

function program4(depth0,data) {
  
  var buffer = "", stack1;
  buffer += "<a href=\"/node/";
  if (stack1 = helpers.id) { stack1 = stack1.call(depth0, {hash:{},data:data}); }
  else { stack1 = depth0.id; stack1 = typeof stack1 === functionType ? stack1.apply(depth0) : stack1; }
  buffer += escapeExpression(stack1)
    + "\">";
  return buffer;
  }

function program6(depth0,data) {
  
  var buffer = "", stack1;
  buffer += "<i class=\"icon-calendar ";
  stack1 = helpers['if'].call(depth0, depth0.is_active, {hash:{},inverse:self.noop,fn:self.program(7, program7, data),data:data});
  if(stack1 || stack1 === 0) { buffer += stack1; }
  buffer += "\" title=\"Pacemaker\"></i>";
  return buffer;
  }
function program7(depth0,data) {
  
  
  return "icon-white";
  }

function program9(depth0,data) {
  
  var buffer = "", stack1;
  buffer += "<i class=\"icon-heart ";
  stack1 = helpers['if'].call(depth0, depth0.is_active, {hash:{},inverse:self.noop,fn:self.program(7, program7, data),data:data});
  if(stack1 || stack1 === 0) { buffer += stack1; }
  buffer += "\" title=\"Heart\"></i>";
  return buffer;
  }

function program11(depth0,data) {
  
  var buffer = "", stack1;
  buffer += "<i class=\"icon-random ";
  stack1 = helpers['if'].call(depth0, depth0.is_active, {hash:{},inverse:self.noop,fn:self.program(7, program7, data),data:data});
  if(stack1 || stack1 === 0) { buffer += stack1; }
  buffer += "\" title=\"Router\"></i>";
  return buffer;
  }

function program13(depth0,data) {
  
  
  return "</a>";
  }

  buffer += "<div class=\"application-list\">\n	<ul class=\"nav nav-list\">\n		<li class=\"nav-header\">Nodes</li>\n		";
  stack1 = helpers.each.call(depth0, depth0.nodes, {hash:{},inverse:self.noop,fn:self.program(1, program1, data),data:data});
  if(stack1 || stack1 === 0) { buffer += stack1; }
  buffer += "\n	</ul>\n</div>\n";
  return buffer;
  });
})();(function() {
  var template = Handlebars.template, templates = Handlebars.templates = Handlebars.templates || {};
templates['app_menu'] = template(function (Handlebars,depth0,helpers,partials,data) {
  this.compilerInfo = [2,'>= 1.0.0-rc.3'];
helpers = helpers || Handlebars.helpers; data = data || {};
  var buffer = "", stack1, stack2, self=this, functionType="function", escapeExpression=this.escapeExpression;

function program1(depth0,data) {
  
  var buffer = "", stack1, stack2;
  buffer += "\n			<li class=\"application ";
  stack1 = helpers['if'].call(depth0, depth0.is_active, {hash:{},inverse:self.noop,fn:self.program(2, program2, data),data:data});
  if(stack1 || stack1 === 0) { buffer += stack1; }
  buffer += "\" data-application-id=\"";
  if (stack1 = helpers.id) { stack1 = stack1.call(depth0, {hash:{},data:data}); }
  else { stack1 = depth0.id; stack1 = typeof stack1 === functionType ? stack1.apply(depth0) : stack1; }
  buffer += escapeExpression(stack1)
    + "\">\n				<a href=\"/application/";
  if (stack1 = helpers.id) { stack1 = stack1.call(depth0, {hash:{},data:data}); }
  else { stack1 = depth0.id; stack1 = typeof stack1 === functionType ? stack1.apply(depth0) : stack1; }
  buffer += escapeExpression(stack1)
    + "\">\n					<span class=\"application-list-state\">\n						<span class=\"badge "
    + escapeExpression(((stack1 = ((stack1 = depth0.health_class),stack1 == null || stack1 === false ? stack1 : stack1.badge)),typeof stack1 === functionType ? stack1.apply(depth0) : stack1))
    + "\" title=\"Health: ";
  if (stack2 = helpers.health) { stack2 = stack2.call(depth0, {hash:{},data:data}); }
  else { stack2 = depth0.health; stack2 = typeof stack2 === functionType ? stack2.apply(depth0) : stack2; }
  buffer += escapeExpression(stack2)
    + "\"><i class=\""
    + escapeExpression(((stack1 = ((stack1 = depth0.health_class),stack1 == null || stack1 === false ? stack1 : stack1.icon)),typeof stack1 === functionType ? stack1.apply(depth0) : stack1))
    + " icon-white\"></i></span>\n						<!-- "
    + escapeExpression(((stack1 = ((stack1 = depth0.services),stack1 == null || stack1 === false ? stack1 : stack1.length)),typeof stack1 === functionType ? stack1.apply(depth0) : stack1))
    + "&nbsp;service(s) -->\n					</span>\n					<span class=\"application-list-name\">";
  if (stack2 = helpers.name) { stack2 = stack2.call(depth0, {hash:{},data:data}); }
  else { stack2 = depth0.name; stack2 = typeof stack2 === functionType ? stack2.apply(depth0) : stack2; }
  buffer += escapeExpression(stack2)
    + "</span>\n					<ul class=\"application-list-versions\">\n\n					</ul>\n				</a>\n			</li>\n			<li class=\"divider\"></li>\n		";
  return buffer;
  }
function program2(depth0,data) {
  
  
  return "active";
  }

function program4(depth0,data) {
  
  
  return "\n			<li class=\"no-menu-items\">No applications in this workspace</li>\n			<li class=\"divider\"></li>\n		";
  }

function program6(depth0,data) {
  
  
  return "class=\"active\"";
  }

  buffer += "<div class=\"application-list\">\n	<ul class=\"nav nav-list\">\n		<li class=\"nav-header\">Applications: "
    + escapeExpression(((stack1 = ((stack1 = depth0.workspace),stack1 == null || stack1 === false ? stack1 : stack1.name)),typeof stack1 === functionType ? stack1.apply(depth0) : stack1))
    + "</li>\n		";
  stack2 = helpers.each.call(depth0, depth0.applications, {hash:{},inverse:self.noop,fn:self.program(1, program1, data),data:data});
  if(stack2 || stack2 === 0) { buffer += stack2; }
  buffer += "\n		";
  stack2 = helpers.unless.call(depth0, ((stack1 = depth0.applications),stack1 == null || stack1 === false ? stack1 : stack1.length), {hash:{},inverse:self.noop,fn:self.program(4, program4, data),data:data});
  if(stack2 || stack2 === 0) { buffer += stack2; }
  buffer += "\n		<li ";
  stack2 = helpers['if'].call(depth0, depth0.new_application_active, {hash:{},inverse:self.noop,fn:self.program(6, program6, data),data:data});
  if(stack2 || stack2 === 0) { buffer += stack2; }
  buffer += "><a href=\"/workspace/"
    + escapeExpression(((stack1 = ((stack1 = depth0.workspace),stack1 == null || stack1 === false ? stack1 : stack1.id)),typeof stack1 === functionType ? stack1.apply(depth0) : stack1))
    + "/applications/new\">Create Application</a></li>\n	</ul>\n</div>\n";
  return buffer;
  });
})();(function() {
  var template = Handlebars.template, templates = Handlebars.templates = Handlebars.templates || {};
templates['app_menu_versions'] = template(function (Handlebars,depth0,helpers,partials,data) {
  this.compilerInfo = [2,'>= 1.0.0-rc.3'];
helpers = helpers || Handlebars.helpers; data = data || {};
  var buffer = "", stack1, self=this, functionType="function", escapeExpression=this.escapeExpression;

function program1(depth0,data) {
  
  var buffer = "", stack1;
  buffer += "\n	<li class=\"version ";
  stack1 = helpers['if'].call(depth0, depth0.is_active, {hash:{},inverse:self.noop,fn:self.program(2, program2, data),data:data});
  if(stack1 || stack1 === 0) { buffer += stack1; }
  buffer += "\" data-version-id=\"";
  if (stack1 = helpers.id) { stack1 = stack1.call(depth0, {hash:{},data:data}); }
  else { stack1 = depth0.id; stack1 = typeof stack1 === functionType ? stack1.apply(depth0) : stack1; }
  buffer += escapeExpression(stack1)
    + "\">\n		<a href=\"/version/";
  if (stack1 = helpers.id) { stack1 = stack1.call(depth0, {hash:{},data:data}); }
  else { stack1 = depth0.id; stack1 = typeof stack1 === functionType ? stack1.apply(depth0) : stack1; }
  buffer += escapeExpression(stack1)
    + "\">\n			<span class=\"application-list-version\">\n				Version ";
  if (stack1 = helpers.version) { stack1 = stack1.call(depth0, {hash:{},data:data}); }
  else { stack1 = depth0.version; stack1 = typeof stack1 === functionType ? stack1.apply(depth0) : stack1; }
  buffer += escapeExpression(stack1)
    + "\n				";
  stack1 = helpers['if'].call(depth0, depth0.is_current, {hash:{},inverse:self.noop,fn:self.program(4, program4, data),data:data});
  if(stack1 || stack1 === 0) { buffer += stack1; }
  buffer += "\n			</span>\n		</a>\n	</li>\n";
  return buffer;
  }
function program2(depth0,data) {
  
  
  return "active";
  }

function program4(depth0,data) {
  
  var buffer = "", stack1;
  buffer += "\n					<i class=\"icon-star ";
  stack1 = helpers['if'].call(depth0, depth0.is_active, {hash:{},inverse:self.noop,fn:self.program(5, program5, data),data:data});
  if(stack1 || stack1 === 0) { buffer += stack1; }
  buffer += "\" title=\"Version is current\"></i>\n				";
  return buffer;
  }
function program5(depth0,data) {
  
  
  return "icon-white";
  }

  stack1 = helpers.each.call(depth0, depth0.versions, {hash:{},inverse:self.noop,fn:self.program(1, program1, data),data:data});
  if(stack1 || stack1 === 0) { buffer += stack1; }
  buffer += "\n";
  return buffer;
  });
})();(function() {
  var template = Handlebars.template, templates = Handlebars.templates = Handlebars.templates || {};
templates['role_allocation_list'] = template(function (Handlebars,depth0,helpers,partials,data) {
  this.compilerInfo = [2,'>= 1.0.0-rc.3'];
helpers = helpers || Handlebars.helpers; data = data || {};
  var buffer = "", stack1, functionType="function", escapeExpression=this.escapeExpression, self=this;

function program1(depth0,data) {
  
  var buffer = "", stack1, stack2;
  buffer += "\n		<tr>\n			<td>\n				<a href=\"/user/"
    + escapeExpression(((stack1 = ((stack1 = depth0.user),stack1 == null || stack1 === false ? stack1 : stack1.id)),typeof stack1 === functionType ? stack1.apply(depth0) : stack1))
    + "\">\n					"
    + escapeExpression(((stack1 = ((stack1 = depth0.user),stack1 == null || stack1 === false ? stack1 : stack1.name)),typeof stack1 === functionType ? stack1.apply(depth0) : stack1))
    + "\n				</a>\n			</td>\n			<td>\n				<a href=\"/role/"
    + escapeExpression(((stack1 = ((stack1 = depth0.role),stack1 == null || stack1 === false ? stack1 : stack1.id)),typeof stack1 === functionType ? stack1.apply(depth0) : stack1))
    + "\">\n					"
    + escapeExpression(((stack1 = ((stack1 = depth0.role),stack1 == null || stack1 === false ? stack1 : stack1.name)),typeof stack1 === functionType ? stack1.apply(depth0) : stack1))
    + "\n				</a>\n			</td>\n			<td>\n				";
  stack2 = helpers['if'].call(depth0, depth0.workspace, {hash:{},inverse:self.program(4, program4, data),fn:self.program(2, program2, data),data:data});
  if(stack2 || stack2 === 0) { buffer += stack2; }
  buffer += "\n			</td>\n			<td>\n				<div class=\"table-button-box\">\n					<form method=\"POST\" action=\"/role/allocation/unassign\">\n						<input type=\"hidden\" name=\"allocation_id\" value=\"";
  if (stack2 = helpers.id) { stack2 = stack2.call(depth0, {hash:{},data:data}); }
  else { stack2 = depth0.id; stack2 = typeof stack2 === functionType ? stack2.apply(depth0) : stack2; }
  buffer += escapeExpression(stack2)
    + "\" />\n						<input type=\"submit\" class=\"btn btn-mini btn-danger\" value=\"Remove\" />\n					</form>\n				</div>\n			</td>\n		</tr>\n	";
  return buffer;
  }
function program2(depth0,data) {
  
  var buffer = "", stack1;
  buffer += "\n					<a href=\"/workspace/"
    + escapeExpression(((stack1 = ((stack1 = depth0.workspace),stack1 == null || stack1 === false ? stack1 : stack1.id)),typeof stack1 === functionType ? stack1.apply(depth0) : stack1))
    + "\">\n						"
    + escapeExpression(((stack1 = ((stack1 = depth0.workspace),stack1 == null || stack1 === false ? stack1 : stack1.name)),typeof stack1 === functionType ? stack1.apply(depth0) : stack1))
    + "\n					</a>\n				";
  return buffer;
  }

function program4(depth0,data) {
  
  
  return "\n					Global\n				";
  }

  buffer += "<h1>Role Allocation List</h1>\n\n<div class=\"btn-group btn-group-header\">\n	<a href=\"/role/allocation/assign\" class=\"btn\"><i class=\"icon-list-alt\"></i> Allocate</a>\n</div>\n\n<table class=\"table table-striped table-bordered\">\n	<tr>\n		<th>User</th>\n		<th>Role</th>\n		<th>Workspace</th>\n		<th>Action</th>\n	</tr>\n	";
  stack1 = helpers.each.call(depth0, depth0.allocations, {hash:{},inverse:self.noop,fn:self.program(1, program1, data),data:data});
  if(stack1 || stack1 === 0) { buffer += stack1; }
  buffer += "\n</table>\n";
  return buffer;
  });
})();(function() {
  var template = Handlebars.template, templates = Handlebars.templates = Handlebars.templates || {};
templates['role_list'] = template(function (Handlebars,depth0,helpers,partials,data) {
  this.compilerInfo = [2,'>= 1.0.0-rc.3'];
helpers = helpers || Handlebars.helpers; data = data || {};
  var buffer = "", stack1, stack2, options, functionType="function", escapeExpression=this.escapeExpression, self=this, helperMissing=helpers.helperMissing;

function program1(depth0,data) {
  
  
  return "\n		<a class=\"btn\" href=\"/role/create\"><i class=\"icon-plus\"></i> Create Role</a>\n	";
  }

function program3(depth0,data) {
  
  var buffer = "", stack1, stack2, options;
  buffer += "\n		<tr>\n			<td>\n				";
  options = {hash:{},inverse:self.noop,fn:self.program(4, program4, data),data:data};
  stack2 = ((stack1 = helpers.ifPermission),stack1 ? stack1.call(depth0, "ROLE_EDIT", options) : helperMissing.call(depth0, "ifPermission", "ROLE_EDIT", options));
  if(stack2 || stack2 === 0) { buffer += stack2; }
  buffer += "\n					";
  if (stack2 = helpers.name) { stack2 = stack2.call(depth0, {hash:{},data:data}); }
  else { stack2 = depth0.name; stack2 = typeof stack2 === functionType ? stack2.apply(depth0) : stack2; }
  buffer += escapeExpression(stack2)
    + "\n				";
  options = {hash:{},inverse:self.noop,fn:self.program(6, program6, data),data:data};
  stack2 = ((stack1 = helpers.ifPermission),stack1 ? stack1.call(depth0, "ROLE_EDIT", options) : helperMissing.call(depth0, "ifPermission", "ROLE_EDIT", options));
  if(stack2 || stack2 === 0) { buffer += stack2; }
  buffer += "\n			</td>\n			<td>\n				<ul>\n					";
  stack2 = helpers.each.call(depth0, depth0.permissions, {hash:{},inverse:self.noop,fn:self.program(8, program8, data),data:data});
  if(stack2 || stack2 === 0) { buffer += stack2; }
  buffer += "\n				</ul>\n			</td>\n		</tr>\n	";
  return buffer;
  }
function program4(depth0,data) {
  
  var buffer = "", stack1;
  buffer += "<a href=\"/role/";
  if (stack1 = helpers.id) { stack1 = stack1.call(depth0, {hash:{},data:data}); }
  else { stack1 = depth0.id; stack1 = typeof stack1 === functionType ? stack1.apply(depth0) : stack1; }
  buffer += escapeExpression(stack1)
    + "\">";
  return buffer;
  }

function program6(depth0,data) {
  
  
  return "</a>";
  }

function program8(depth0,data) {
  
  var buffer = "";
  buffer += "\n						<li>"
    + escapeExpression((typeof depth0 === functionType ? depth0.apply(depth0) : depth0))
    + "</li>\n					";
  return buffer;
  }

  buffer += "<h1>Role List</h1>\n\n<div class=\"btn-group btn-group-header\">\n	";
  options = {hash:{},inverse:self.noop,fn:self.program(1, program1, data),data:data};
  stack2 = ((stack1 = helpers.ifPermission),stack1 ? stack1.call(depth0, "ROLE_EDIT", options) : helperMissing.call(depth0, "ifPermission", "ROLE_EDIT", options));
  if(stack2 || stack2 === 0) { buffer += stack2; }
  buffer += "\n</div>\n\n<table class=\"table table-striped table-bordered\">\n	<tr>\n		<th>Name</th>\n		<th>Permissions</th>\n	</tr>\n	";
  stack2 = helpers.each.call(depth0, depth0.roles, {hash:{},inverse:self.noop,fn:self.program(3, program3, data),data:data});
  if(stack2 || stack2 === 0) { buffer += stack2; }
  buffer += "\n</table>\n";
  return buffer;
  });
})();(function() {
  var template = Handlebars.template, templates = Handlebars.templates = Handlebars.templates || {};
templates['user_list'] = template(function (Handlebars,depth0,helpers,partials,data) {
  this.compilerInfo = [2,'>= 1.0.0-rc.3'];
helpers = helpers || Handlebars.helpers; data = data || {};
  var buffer = "", stack1, stack2, options, functionType="function", escapeExpression=this.escapeExpression, self=this, helperMissing=helpers.helperMissing;

function program1(depth0,data) {
  
  
  return "\n		<a class=\"btn\" href=\"/user/create\"><i class=\"icon-plus\"></i> Create User</a>\n	";
  }

function program3(depth0,data) {
  
  var buffer = "", stack1, stack2, options;
  buffer += "\n		<tr>\n			<td>\n				";
  options = {hash:{},inverse:self.noop,fn:self.program(4, program4, data),data:data};
  stack2 = ((stack1 = helpers.ifPermission),stack1 ? stack1.call(depth0, "USER_EDIT", options) : helperMissing.call(depth0, "ifPermission", "USER_EDIT", options));
  if(stack2 || stack2 === 0) { buffer += stack2; }
  buffer += "\n					";
  if (stack2 = helpers.name) { stack2 = stack2.call(depth0, {hash:{},data:data}); }
  else { stack2 = depth0.name; stack2 = typeof stack2 === functionType ? stack2.apply(depth0) : stack2; }
  buffer += escapeExpression(stack2)
    + "\n				";
  options = {hash:{},inverse:self.noop,fn:self.program(6, program6, data),data:data};
  stack2 = ((stack1 = helpers.ifPermission),stack1 ? stack1.call(depth0, "USER_EDIT", options) : helperMissing.call(depth0, "ifPermission", "USER_EDIT", options));
  if(stack2 || stack2 === 0) { buffer += stack2; }
  buffer += "\n			</td>\n			<td>\n				";
  if (stack2 = helpers.auth_source) { stack2 = stack2.call(depth0, {hash:{},data:data}); }
  else { stack2 = depth0.auth_source; stack2 = typeof stack2 === functionType ? stack2.apply(depth0) : stack2; }
  buffer += escapeExpression(stack2)
    + "\n			</td>\n			<td>\n				";
  if (stack2 = helpers.login) { stack2 = stack2.call(depth0, {hash:{},data:data}); }
  else { stack2 = depth0.login; stack2 = typeof stack2 === functionType ? stack2.apply(depth0) : stack2; }
  buffer += escapeExpression(stack2)
    + "\n			</td>\n			<td title=\""
    + escapeExpression(((stack1 = ((stack1 = depth0.created_moment),stack1 == null || stack1 === false ? stack1 : stack1.format)),typeof stack1 === functionType ? stack1.apply(depth0) : stack1))
    + "\">\n				"
    + escapeExpression(((stack1 = ((stack1 = depth0.created_moment),stack1 == null || stack1 === false ? stack1 : stack1.calendar)),typeof stack1 === functionType ? stack1.apply(depth0) : stack1))
    + "\n			</td>\n			<td>\n				";
  stack2 = helpers['if'].call(depth0, depth0.enabled, {hash:{},inverse:self.program(10, program10, data),fn:self.program(8, program8, data),data:data});
  if(stack2 || stack2 === 0) { buffer += stack2; }
  buffer += "\n			</td>\n		</tr>\n	";
  return buffer;
  }
function program4(depth0,data) {
  
  var buffer = "", stack1;
  buffer += "<a href=\"/user/";
  if (stack1 = helpers.id) { stack1 = stack1.call(depth0, {hash:{},data:data}); }
  else { stack1 = depth0.id; stack1 = typeof stack1 === functionType ? stack1.apply(depth0) : stack1; }
  buffer += escapeExpression(stack1)
    + "\">";
  return buffer;
  }

function program6(depth0,data) {
  
  
  return "</a>";
  }

function program8(depth0,data) {
  
  
  return "\n					Enabled\n				";
  }

function program10(depth0,data) {
  
  
  return "\n					Disabled\n				";
  }

  buffer += "<h1>User List</h1>\n\n<div class=\"btn-group btn-group-header\">\n	";
  options = {hash:{},inverse:self.noop,fn:self.program(1, program1, data),data:data};
  stack2 = ((stack1 = helpers.ifPermission),stack1 ? stack1.call(depth0, "USER_EDIT", options) : helperMissing.call(depth0, "ifPermission", "USER_EDIT", options));
  if(stack2 || stack2 === 0) { buffer += stack2; }
  buffer += "\n</div>\n\n<table class=\"table table-striped table-bordered\">\n	<tr>\n		<th>Name</th>\n		<th>Authentication Method</th>\n		<th>Login</th>\n		<th>Created</th>\n		<th>Enabled</th>\n	</tr>\n	";
  stack2 = helpers.each.call(depth0, depth0.users, {hash:{},inverse:self.noop,fn:self.program(3, program3, data),data:data});
  if(stack2 || stack2 === 0) { buffer += stack2; }
  buffer += "\n</table>\n";
  return buffer;
  });
})();(function() {
  var template = Handlebars.template, templates = Handlebars.templates = Handlebars.templates || {};
templates['user_profile'] = template(function (Handlebars,depth0,helpers,partials,data) {
  this.compilerInfo = [2,'>= 1.0.0-rc.3'];
helpers = helpers || Handlebars.helpers; data = data || {};
  var buffer = "", stack1, functionType="function", escapeExpression=this.escapeExpression;


  buffer += "<h1>Profile</h1>\n\n	<p class=\"lead\">Your API key: ";
  if (stack1 = helpers.apikey) { stack1 = stack1.call(depth0, {hash:{},data:data}); }
  else { stack1 = depth0.apikey; stack1 = typeof stack1 === functionType ? stack1.apply(depth0) : stack1; }
  buffer += escapeExpression(stack1)
    + "</p>\n\n	<form method=\"post\" action=\"/profile/reset-api-key\"><button class=\"btn\">Reset API key</button></form>\n";
  return buffer;
  });
})();(function() {
  var template = Handlebars.template, templates = Handlebars.templates = Handlebars.templates || {};
templates['configuration_dump'] = template(function (Handlebars,depth0,helpers,partials,data) {
  this.compilerInfo = [2,'>= 1.0.0-rc.3'];
helpers = helpers || Handlebars.helpers; data = data || {};
  var buffer = "", stack1, functionType="function", escapeExpression=this.escapeExpression;


  buffer += "<h1>Configuration Dump</h1>\n<pre>";
  if (stack1 = helpers.configuration) { stack1 = stack1.call(depth0, {hash:{},data:data}); }
  else { stack1 = depth0.configuration; stack1 = typeof stack1 === functionType ? stack1.apply(depth0) : stack1; }
  buffer += escapeExpression(stack1)
    + "</pre>\n";
  return buffer;
  });
})();(function() {
  var template = Handlebars.template, templates = Handlebars.templates = Handlebars.templates || {};
templates['configuration_plugins'] = template(function (Handlebars,depth0,helpers,partials,data) {
  this.compilerInfo = [2,'>= 1.0.0-rc.3'];
helpers = helpers || Handlebars.helpers; data = data || {};
  var buffer = "", stack1, functionType="function", escapeExpression=this.escapeExpression, self=this;

function program1(depth0,data) {
  
  var buffer = "", stack1;
  buffer += "\n				<tr>\n					<td><strong>";
  if (stack1 = helpers.title) { stack1 = stack1.call(depth0, {hash:{},data:data}); }
  else { stack1 = depth0.title; stack1 = typeof stack1 === functionType ? stack1.apply(depth0) : stack1; }
  buffer += escapeExpression(stack1)
    + "</strong></td>\n					<td>";
  if (stack1 = helpers.name) { stack1 = stack1.call(depth0, {hash:{},data:data}); }
  else { stack1 = depth0.name; stack1 = typeof stack1 === functionType ? stack1.apply(depth0) : stack1; }
  buffer += escapeExpression(stack1)
    + "</td>\n					<td>\n						";
  stack1 = helpers['if'].call(depth0, depth0.options, {hash:{},inverse:self.noop,fn:self.program(2, program2, data),data:data});
  if(stack1 || stack1 === 0) { buffer += stack1; }
  buffer += "\n					</td>\n					<td><ul>\n						";
  stack1 = helpers.each.call(depth0, depth0.modes, {hash:{},inverse:self.noop,fn:self.program(4, program4, data),data:data});
  if(stack1 || stack1 === 0) { buffer += stack1; }
  buffer += "\n					</ul></td>\n				</tr>\n		";
  return buffer;
  }
function program2(depth0,data) {
  
  var buffer = "", stack1;
  buffer += "\n							<pre>";
  if (stack1 = helpers.options) { stack1 = stack1.call(depth0, {hash:{},data:data}); }
  else { stack1 = depth0.options; stack1 = typeof stack1 === functionType ? stack1.apply(depth0) : stack1; }
  buffer += escapeExpression(stack1)
    + "</pre>\n						";
  return buffer;
  }

function program4(depth0,data) {
  
  var buffer = "";
  buffer += "\n							<li>"
    + escapeExpression((typeof depth0 === functionType ? depth0.apply(depth0) : depth0))
    + "</li>\n						";
  return buffer;
  }

  buffer += "<h1>Active Plugins</h1>\n\n	<table class=\"table table-striped table-bordered\">\n		<tr>\n			<th>Plugin</th>\n			<th>Symbolic Name</th>\n			<th>Configuration</th>\n			<th>Available Modes</th>\n		</tr>\n\n		";
  stack1 = helpers.each.call(depth0, depth0.plugins, {hash:{},inverse:self.noop,fn:self.program(1, program1, data),data:data});
  if(stack1 || stack1 === 0) { buffer += stack1; }
  buffer += "\n	</table>\n\n";
  return buffer;
  });
})();(function() {
  var template = Handlebars.template, templates = Handlebars.templates = Handlebars.templates || {};
templates['workspace_main'] = template(function (Handlebars,depth0,helpers,partials,data) {
  this.compilerInfo = [2,'>= 1.0.0-rc.3'];
helpers = helpers || Handlebars.helpers; data = data || {};
  var buffer = "", stack1, stack2, options, functionType="function", escapeExpression=this.escapeExpression, self=this, helperMissing=helpers.helperMissing;

function program1(depth0,data) {
  
  var buffer = "", stack1;
  buffer += "\n			<div class=\"btn-group btn-group-header\">\n				<a class=\"btn\" href=\"/workspace/"
    + escapeExpression(((stack1 = ((stack1 = depth0.workspace),stack1 == null || stack1 === false ? stack1 : stack1.id)),typeof stack1 === functionType ? stack1.apply(depth0) : stack1))
    + "\"><i class=\"icon-edit\"></i> Edit Workspace</a>\n			</div>\n		";
  return buffer;
  }

  buffer += "<h1>Workspace: "
    + escapeExpression(((stack1 = ((stack1 = depth0.workspace),stack1 == null || stack1 === false ? stack1 : stack1.name)),typeof stack1 === functionType ? stack1.apply(depth0) : stack1))
    + "</h1>\n<div class=\"btn-toolbar\">\n		";
  options = {hash:{},inverse:self.noop,fn:self.program(1, program1, data),data:data};
  stack2 = ((stack1 = helpers.ifPermission),stack1 ? stack1.call(depth0, "WORKSPACE_EDIT", ((stack1 = depth0.workspace),stack1 == null || stack1 === false ? stack1 : stack1.id), options) : helperMissing.call(depth0, "ifPermission", "WORKSPACE_EDIT", ((stack1 = depth0.workspace),stack1 == null || stack1 === false ? stack1 : stack1.id), options));
  if(stack2 || stack2 === 0) { buffer += stack2; }
  buffer += "\n	<div class=\"btn-group btn-group-header\">\n		<a class=\"btn\" href=\"/workspace/"
    + escapeExpression(((stack1 = ((stack1 = depth0.workspace),stack1 == null || stack1 === false ? stack1 : stack1.id)),typeof stack1 === functionType ? stack1.apply(depth0) : stack1))
    + "/applications/new\"><i class=\"icon-plus\"></i> Create Application</a>\n	</div>\n	<div class=\"btn-group btn-group-header\">\n		<a class=\"btn\" href=\"/job/list/workspace/"
    + escapeExpression(((stack1 = ((stack1 = depth0.workspace),stack1 == null || stack1 === false ? stack1 : stack1.id)),typeof stack1 === functionType ? stack1.apply(depth0) : stack1))
    + "\">All Jobs</a>\n		<a class=\"btn\" href=\"/job/list/workspace/"
    + escapeExpression(((stack1 = ((stack1 = depth0.workspace),stack1 == null || stack1 === false ? stack1 : stack1.id)),typeof stack1 === functionType ? stack1.apply(depth0) : stack1))
    + "?sub=cron\">Cron Jobs</a>\n	</div>\n</div>\n\n<div class=\"workspace-overview\">\n	<div class=\"overview-graph\" data-name=\"workspace\" data-inputid=\""
    + escapeExpression(((stack1 = ((stack1 = depth0.workspace),stack1 == null || stack1 === false ? stack1 : stack1.id)),typeof stack1 === functionType ? stack1.apply(depth0) : stack1))
    + "\" data-metric=\"requests_by_code\">\n		<h3>Requests by Response Code</h3>\n		<div class=\"graph-container\"><br><br>Loading ...</div>\n	</div>\n	<!--<div class=\"overview-graph\" data-name=\"workspace\" data-inputid=\""
    + escapeExpression(((stack1 = ((stack1 = depth0.workspace),stack1 == null || stack1 === false ? stack1 : stack1.id)),typeof stack1 === functionType ? stack1.apply(depth0) : stack1))
    + "\" data-metric=\"requests\">\n		<h3>Requests</h3>\n		<div class=\"graph-container\"><br><br>Loading ...</div>\n	</div>-->\n	<div class=\"overview-graph\" data-name=\"workspace\" data-inputid=\""
    + escapeExpression(((stack1 = ((stack1 = depth0.workspace),stack1 == null || stack1 === false ? stack1 : stack1.id)),typeof stack1 === functionType ? stack1.apply(depth0) : stack1))
    + "\" data-metric=\"bytes\">\n		<h3>Bytes Transferred</h3>\n		<div class=\"graph-container\"><br><br>Loading ...</div>\n	</div>\n	<!--<div class=\"overview-graph\" data-name=\"workspace\" data-inputid=\""
    + escapeExpression(((stack1 = ((stack1 = depth0.workspace),stack1 == null || stack1 === false ? stack1 : stack1.id)),typeof stack1 === functionType ? stack1.apply(depth0) : stack1))
    + "\" data-metric=\"time\">\n		<h3>Request time</h3>\n		<div class=\"graph-container\"><br><br>Loading ...</div>\n	</div>-->\n\n	<table class=\"table table-bordered jobs\">\n		<tr>\n			<th>\n				Jobs\n				<div class=\"all-jobs-button\">\n					<a class=\"btn btn-mini\" href=\"/job/list/workspace/"
    + escapeExpression(((stack1 = ((stack1 = depth0.workspace),stack1 == null || stack1 === false ? stack1 : stack1.id)),typeof stack1 === functionType ? stack1.apply(depth0) : stack1))
    + "\">View All</a>\n				</div>\n			</th>\n		</tr>\n		<tr>\n			<td>\n				<div class=\"well job-overview\"></div>\n			</td>\n		</tr>\n	</table>\n</div>\n";
  return buffer;
  });
})();(function() {
  var template = Handlebars.template, templates = Handlebars.templates = Handlebars.templates || {};
templates['workspace_edit'] = template(function (Handlebars,depth0,helpers,partials,data) {
  this.compilerInfo = [2,'>= 1.0.0-rc.3'];
helpers = helpers || Handlebars.helpers; data = data || {};
  var buffer = "", stack1, stack2, functionType="function", escapeExpression=this.escapeExpression, self=this;

function program1(depth0,data) {
  
  var buffer = "", stack1;
  buffer += "\n	<ul class=\"breadcrumb\"></ul>\n	<h1>Edit: "
    + escapeExpression(((stack1 = ((stack1 = depth0.workspace),stack1 == null || stack1 === false ? stack1 : stack1.name)),typeof stack1 === functionType ? stack1.apply(depth0) : stack1))
    + "</h1>\n";
  return buffer;
  }

function program3(depth0,data) {
  
  
  return "\n	<h1>Create Workspace</h1>\n";
  }

  stack2 = helpers['if'].call(depth0, ((stack1 = depth0.workspace),stack1 == null || stack1 === false ? stack1 : stack1.id), {hash:{},inverse:self.program(3, program3, data),fn:self.program(1, program1, data),data:data});
  if(stack2 || stack2 === 0) { buffer += stack2; }
  buffer += "\n\n<!--<link href=\"/css/tag_editor.css\" rel=\"stylesheet\">\n<script src=\"/js/libs/jquery.jsoneditor.js\"></script>-->\n\n<form method=\"POST\" class=\"workspace-edit\">\n	<label for=\"name\">Name:</label>\n	<input name=\"name\" id=\"workspace_name\" type=\"text\" value=\""
    + escapeExpression(((stack1 = ((stack1 = depth0.workspace),stack1 == null || stack1 === false ? stack1 : stack1.name)),typeof stack1 === functionType ? stack1.apply(depth0) : stack1))
    + "\" />\n	<!-- {% raw format_form_error('name') %} -->\n\n	<label for=\"stub\">Stub:</label>\n	<input name=\"stub\" id=\"workspace_stub\" type=\"text\" value=\""
    + escapeExpression(((stack1 = ((stack1 = depth0.workspace),stack1 == null || stack1 === false ? stack1 : stack1.stub)),typeof stack1 === functionType ? stack1.apply(depth0) : stack1))
    + "\" />\n	<!-- {% raw format_form_error('stub') %} -->\n\n	<input type=\"hidden\" id=\"workspace_tags\" name=\"serialised_tags\" value=\"\">\n	<div class=\"workspace-tag-editor pm-tag-editor well\"></div>\n	<!-- {% raw format_form_error('tags') %} -->\n\n	<a class=\"btn btn-success job-action-button\" href=\"#\">Submit</a>\n</form>\n";
  return buffer;
  });
})();(function() {
  var template = Handlebars.template, templates = Handlebars.templates = Handlebars.templates || {};
templates['router_stats_section'] = template(function (Handlebars,depth0,helpers,partials,data) {
  this.compilerInfo = [2,'>= 1.0.0-rc.3'];
helpers = helpers || Handlebars.helpers; data = data || {};
  var buffer = "", stack1, functionType="function", escapeExpression=this.escapeExpression, self=this;

function program1(depth0,data) {
  
  var buffer = "", stack1;
  buffer += "\n	<div class=\"stats-row clearfix\">\n		<span class=\"title\">";
  if (stack1 = helpers.title) { stack1 = stack1.call(depth0, {hash:{},data:data}); }
  else { stack1 = depth0.title; stack1 = typeof stack1 === functionType ? stack1.apply(depth0) : stack1; }
  buffer += escapeExpression(stack1)
    + ":</span>\n		<span class=\"value\">";
  if (stack1 = helpers.value) { stack1 = stack1.call(depth0, {hash:{},data:data}); }
  else { stack1 = depth0.value; stack1 = typeof stack1 === functionType ? stack1.apply(depth0) : stack1; }
  buffer += escapeExpression(stack1)
    + "\n			";
  stack1 = helpers['if'].call(depth0, depth0.unit, {hash:{},inverse:self.noop,fn:self.program(2, program2, data),data:data});
  if(stack1 || stack1 === 0) { buffer += stack1; }
  buffer += "\n			";
  stack1 = helpers['if'].call(depth0, depth0.diff, {hash:{},inverse:self.noop,fn:self.program(4, program4, data),data:data});
  if(stack1 || stack1 === 0) { buffer += stack1; }
  buffer += "\n		</span>\n	</div>\n";
  return buffer;
  }
function program2(depth0,data) {
  
  var buffer = "", stack1;
  buffer += "<span class=\"unit\">";
  if (stack1 = helpers.unit) { stack1 = stack1.call(depth0, {hash:{},data:data}); }
  else { stack1 = depth0.unit; stack1 = typeof stack1 === functionType ? stack1.apply(depth0) : stack1; }
  buffer += escapeExpression(stack1)
    + "</span>";
  return buffer;
  }

function program4(depth0,data) {
  
  var buffer = "", stack1;
  buffer += " | <span class=\"diff\">";
  if (stack1 = helpers.diff) { stack1 = stack1.call(depth0, {hash:{},data:data}); }
  else { stack1 = depth0.diff; stack1 = typeof stack1 === functionType ? stack1.apply(depth0) : stack1; }
  buffer += escapeExpression(stack1)
    + "/s</span>";
  return buffer;
  }

  stack1 = helpers.each.call(depth0, depth0.statset, {hash:{},inverse:self.noop,fn:self.program(1, program1, data),data:data});
  if(stack1 || stack1 === 0) { buffer += stack1; }
  return buffer;
  });
})();(function() {
  var template = Handlebars.template, templates = Handlebars.templates = Handlebars.templates || {};
templates['job_list'] = template(function (Handlebars,depth0,helpers,partials,data) {
  this.compilerInfo = [2,'>= 1.0.0-rc.3'];
helpers = helpers || Handlebars.helpers; data = data || {};
  var buffer = "", stack1, stack2, functionType="function", escapeExpression=this.escapeExpression, self=this;

function program1(depth0,data) {
  
  
  return "<ul class=\"breadcrumb\"></ul>";
  }

function program3(depth0,data) {
  
  var buffer = "", stack1;
  buffer += "<h1>";
  if (stack1 = helpers.title) { stack1 = stack1.call(depth0, {hash:{},data:data}); }
  else { stack1 = depth0.title; stack1 = typeof stack1 === functionType ? stack1.apply(depth0) : stack1; }
  if(stack1 || stack1 === 0) { buffer += stack1; }
  buffer += "</h1>";
  return buffer;
  }

function program5(depth0,data) {
  
  var buffer = "";
  buffer += "\n	<div class=\"job-root well well-small\" data-job=\""
    + escapeExpression((typeof depth0 === functionType ? depth0.apply(depth0) : depth0))
    + "\">\n		Loading...\n	</div>\n";
  return buffer;
  }

function program7(depth0,data) {
  
  
  return "\n	<div class=\"well\">\n		No jobs to display.\n	</div>\n";
  }

  stack1 = helpers['if'].call(depth0, depth0.show_breadcrumbs, {hash:{},inverse:self.noop,fn:self.program(1, program1, data),data:data});
  if(stack1 || stack1 === 0) { buffer += stack1; }
  buffer += "\n\n";
  stack1 = helpers['if'].call(depth0, depth0.title, {hash:{},inverse:self.noop,fn:self.program(3, program3, data),data:data});
  if(stack1 || stack1 === 0) { buffer += stack1; }
  buffer += "\n\n";
  stack1 = helpers.each.call(depth0, depth0.jobs, {hash:{},inverse:self.noop,fn:self.program(5, program5, data),data:data});
  if(stack1 || stack1 === 0) { buffer += stack1; }
  buffer += "\n\n";
  stack2 = helpers.unless.call(depth0, ((stack1 = depth0.jobs),stack1 == null || stack1 === false ? stack1 : stack1.length), {hash:{},inverse:self.noop,fn:self.program(7, program7, data),data:data});
  if(stack2 || stack2 === 0) { buffer += stack2; }
  buffer += "\n";
  return buffer;
  });
})();
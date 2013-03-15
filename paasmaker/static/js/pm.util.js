
if (!window.pm) { var pm = {}; }	// TODO: module handling

pm.util = (function(){
	var module = {};

	module.hasPermissionFromTable = function(table, permission, workspace_id) {
		// From the given table, figure out if the user has that
		// permission or not.
		// table: an object of values from the server.
		// permission: the string permission name.
		// workspace_id: if supplied, should be an integer that is the
		//   workspace ID to limit the request to.

		var testKeys = [];
		if(workspace_id) {
			testKeys.push('' + workspace_id + '_' + permission);
		}
		testKeys.push('None_' + permission);

		for(var i = 0; i < testKeys.length; i++) {
			if(table[testKeys[i]]) {
				return true;
			}
		}

		return false;
	}

	module.hasPermission = function(permission, workspace_id) {
		// Uses the global permissions store 'currentUserPermissions'.
		return module.hasPermissionFromTable(currentUserPermissions, permission, workspace_id);
	}

	// number_format from: http://phpjs.org/functions/number_format/
	module.number_format = function(number, decimals, dec_point, thousands_sep) {
		number = (number + '').replace(/[^0-9+\-Ee.]/g, '');
		var n = !isFinite(+number) ? 0 : +number,
		prec = !isFinite(+decimals) ? 0 : Math.abs(decimals),
		sep = (typeof thousands_sep === 'undefined') ? ',' : thousands_sep,
		dec = (typeof dec_point === 'undefined') ? '.' : dec_point,
		s = '',
		toFixedFix = function (n, prec) {
			var k = Math.pow(10, prec);
			return '' + Math.round(n * k) / k;
		};
		// Fix for IE parseFloat(0.55).toFixed(0) = 0;
		s = (prec ? toFixedFix(n, prec) : '' + Math.round(n)).split('.');
		if (s[0].length > 3) {
			s[0] = s[0].replace(/\B(?=(?:\d{3})+(?!\d))/g, sep);
		}
		if ((s[1] || '').length < prec) {
			s[1] = s[1] || '';
			s[1] += new Array(prec - s[1].length + 1).join('0');
		}
		return s.join(dec);
	}

	// From: http://stackoverflow.com/questions/661562/how-to-format-a-float-in-javascript
	module.toFixed = function(value, precision) {
		var power = Math.pow(10, precision || 0);
		return (Math.round(value * power) / power).toFixed(precision);
	}

	return module;
}());
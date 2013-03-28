/* Paasmaker - Platform as a Service
 *
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */

// PERMISSIONS SYSTEM

test( "Permissions lookup test - simple", function() {
	var testTable = {
		'None_WORKSPACE_VIEW': true,
	};

	equal(true, pm.util.hasPermissionFromTable(testTable, 'WORKSPACE_VIEW'), "Doesn't have WORKSPACE_VIEW.");
	equal(true, pm.util.hasPermissionFromTable(testTable, 'WORKSPACE_VIEW', 1), "Doesn't have WORKSPACE_VIEW.");
	equal(false, pm.util.hasPermissionFromTable(testTable, 'WORKSPACE_EDIT'), "Does have WORKSPACE_EDIT when should not.");
	equal(false, pm.util.hasPermissionFromTable(testTable, 'WORKSPACE_EDIT', 1), "Does have WORKSPACE_EDIT when should not.");
});

test( "Permissions lookup test - advanced", function() {
	var testTable = {
		'None_WORKSPACE_VIEW': true,
		'1_WORKSPACE_EDIT': true,
	};

	equal(true, pm.util.hasPermissionFromTable(testTable, 'WORKSPACE_VIEW'), "Doesn't have WORKSPACE_VIEW.");
	equal(true, pm.util.hasPermissionFromTable(testTable, 'WORKSPACE_VIEW', 1), "Doesn't have WORKSPACE_VIEW.");
	equal(false, pm.util.hasPermissionFromTable(testTable, 'WORKSPACE_EDIT'), "Has WORKSPACE_EDIT when should not.");
	equal(true, pm.util.hasPermissionFromTable(testTable, 'WORKSPACE_EDIT', 1), "Does not have WORKSPACE_EDIT when should for workspace 1.");
});

Glossary
========

This is a glossary of terms used by Paasmaker.

.. glossary::

	Application
		An application is a collection of :term:`application versions <application version>`
		that maintain a history of that application. The application also defines what
		services the application needs to run.

	Application Version
		An application version is a numbered version of an application. The numbers
		start at 1 and increment each time a new version is :term:`prepared <preparing (an application)>`.
		The version is typically a set of files from a specific revision in your source
		control system, which can be started and stopped on your cluster as you need.
		The version is made up of one or more :term:`instance types <instance type>`
		that define exactly what to run in that version.

	De-Registering
		*De-registering* is the action taken by a heart to remove the instance
		from the filesystem. It can not be de-registered unless it's stopped or
		in the error state. The heart will simply remove all files for the application
		when performing this action.

	Exclusive Instance
		An exclusive instance is started and stopped when the parent version is current.
		When the current version changes, the currently exclusive instance is stopped
		and the new exclusive instance is started up to take it's place.

	Heart
		The subsystem that manages :term:`instances <Instance>` on nodes,
		downloading the files and starting and stopping them as required.

	Instance
		An instance is a single copy of your application. An instance is
		assigned to a specific node where it lives. An instance has a set
		of files, that it gets from a specific version of the code. Instances
		can be started or stopped as required or requested. A typical application
		would have multiple instances for scaling and redundancy. At the end
		of a lifecycle for an instance, it is :term:`De-Registered <de-registering>`
		from the node, which means all of its files are deleted. For this reason,
		instances should not write files inside their root directory unless you
		can lose them; for example, cache files are appropriate to write, but
		uploaded images are not.

	Instance Type
		Some projects have multiple aspects to them, all from the same code base, and Paasmaker
		provides the ability to consider those aspects as one in the form of an
		:term:`application version`. For example, a web project might have the following
		components all in the same code base:

		* A public front end website ("web")
		* An administration area for that website with a different document root ("admin")
		* A background task that listens on a message queue to perform longer running operations as queued up by the public or administrative front end. ("worker")

		In each application version, you can define all of these instance types seperately,
		from the same code base. They can all have different runtimes, different ways to start,
		or different options - but they all utilise and are supplied the application's services.
		By marking certain instance types as :term:`exclusive <exclusive instance>` you
		can ensure that only one version of that instance type is running at a time - for example,
		you might mark the "worker" instance type as exclusive so you don't have two workers
		of different versions running at the same time. Paasmaker will ensure that only the
		current version of the application has an exclusive instance type running.

		Adding this distinction does make Paasmaker more complex, but makes it easier to manage
		applications with multiple components as a single entity.

	Pacemaker
		The subsystem that coordinates all other activities on the cluster,
		and provides the user facing web front end and API.

	Preparing (an application)
		When a new version of an application is deployed, it is prepared first. The goal
		of this task is to fetch the files from somewhere (typically a source control
		system), do any tasks required to build those sources (eg, process CSS/JS files,
		download dependencies for that project, or any other task that is required
		only once for all instances), and then pack those files and store them somewhere
		for Hearts to be able to fetch those files later.

	Registering
		*Registering* is the action taken by a heart to get the instance ready to
		run. This involves downloading the appropriate version of the application
		files, unpacking them to a temporary location, and recording the new
		instance in the heart's runtime database. Once it is registered, it can
		be started or stopped as needed.

	Router
		The subsystem that manages router nodes, that direct incoming
		HTTP requests to an instance that can service that request. This
		node also parses statistics.

	Service
		A *service* is something supplied to an application to allow it to operate.
		For example, a service supplied to an application is a MySQL database - the
		creation or management of that database is up to Paasmaker, and the application
		is simply passed the credentials for the database so it can perform it's task.
		A named service is shared between all applications in a :term:`workspace`.

	Standalone instance
		An instance that doesn't listed on a TCP port; typically a background runner task.
		This type of instance is not supplied with a TCP port nor are any routes added for
		it. It is managed in the same way as other instances, and can have it's own runtime.

	Version
		See :term:`application version <application version>`.

	Workspace
		A workspace is a working area that has a number of :term:`applications <application>`
		applications in it. It is designed as a partition between environments
		(for example, Staging and Production), and also as a base level partition
		for permissions (for example, you could grant only certain staff access
		to the production workspace, but more staff can access staging).

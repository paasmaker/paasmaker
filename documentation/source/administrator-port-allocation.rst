Paasmaker TCP port allocation
=============================

Paasmaker has a set of hard coded default TCP ports that it uses
and assigns to various components to allow them to talk to each other.

All of these ports can be changed via the configuration.

If you want to tightly lock down your systems, you can use the port
map below to adjust your firewalls on individual machines to let them
talk to each other.

+-------------+----------------------------------------------+
| Port        | Description                                  |
+=============+==============================================+
| 42500       | API Requests                                 |
+-------------+----------------------------------------------+
| 42510       | Router Table Redis - Master                  |
+-------------+----------------------------------------------+
| 42511       | Router Table Redis - Slave                   |
+-------------+----------------------------------------------+
| 42512       | Router Stats Redis                           |
+-------------+----------------------------------------------+
| 42513       | Jobs System Redis                            |
+-------------+----------------------------------------------+
| 42530       | NGINX Router Direct Port                     |
+-------------+----------------------------------------------+
| 42531       | NGINX Router Port 80                         |
|             | (sends X-Forwarded-Port: 80 to applications) |
+-------------+----------------------------------------------+
| 42532       | NGINX Router Port 443                        |
|             | (sends X-Forwarded-Port: 443 to applications,|
|             | as well as a X-Forwarded-Proto: https)       |
+-------------+----------------------------------------------+
| 42600-42699 | Pool to assign to application instances      |
+-------------+----------------------------------------------+
| 42700-42799 | Pool for managed services to assign          |
+-------------+----------------------------------------------+
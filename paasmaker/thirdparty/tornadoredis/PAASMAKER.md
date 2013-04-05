Paasmaker's copy of Tornado Redis
=================================

Paasmaker has it's own copy of Tornado Redis, based on version 0.0.7. This is a very
old version, however, as to this moment, the latest version has major issues with our
codebase, so we're using the old version.

This library doesn't support the SCRIPT LOAD command which we needed, so this copy
was taken and then modified. The untouched files were committed in one go, and then
our modifications in a later commit to show just those changes.
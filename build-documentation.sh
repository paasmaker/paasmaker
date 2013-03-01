#!/bin/bash

# Activate the virtualenv.
. thirdparty/python/bin/activate

# Build the HTML docs.
make -C documentation/ html
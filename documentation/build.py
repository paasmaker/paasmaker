#!/usr/bin/env python

import os

from sphinx.websupport import WebSupport

support = WebSupport(srcdir=os.path.abspath('source'),
                     builddir='websupport',
                     search='xapian')

support.build()

import uuid
import time
import logging
import json

import paasmaker
from plugin import MODE, Plugin
from paasmaker.common.core import constants
from ..common.testhelpers import TestHelpers

from pubsub import pub

import tornado
import tornado.testing

import colander

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

# TODO: To the job manager, add the ability to add jobs but not allow them to execute just yet.
# Almost like a transaction - this prevents us half adding a job tree and then having that kicked off
# part way through.


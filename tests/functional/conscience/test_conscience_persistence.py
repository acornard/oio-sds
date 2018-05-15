# Copyright (C) 2015-2018 OpenIO SAS, as part of OpenIO SDS
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3.0 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library.

import os
from subprocess import check_call
import time

from tests.utils import BaseTestCase


def exp(path):
    return os.path.expanduser(path)


class TestConsciencePersistence(BaseTestCase):

    def setUp(self):
        super(TestConsciencePersistence, self).setUp()
        if not self.conf['with_persistence']:
            self.skipTest["Conscience persistence not enabled"]

    def _service(self, name, action):
        name = "%s-%s" % (self.conf['namespace'], name)
        check_call(['gridinit_cmd', '-S',
                    exp('~/.oio/sds/run/gridinit.sock'), action, name])

    def test_conscience_persistence(self):
        self.setUp()
        time.sleep(20)
        self._service('@openio', 'stop')
        self._service('@conscience @proxy', 'start')
        services = self.conf['services']
        for srvtype in services:
            if 'conscience' not in srvtype:
                srv = self.get_service(srvtype)
                self.assertEqual(srv['status'], 'DOWN')
                self.assertGreater(srv['score'], 0)

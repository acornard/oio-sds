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
import json
import time
import subprocess
from tests.utils import BaseTestCase
from tests.utils import CODE_SRVTYPE_NOTMANAGED

def exp(path):
    return os.path.expanduser(path)

class TestConsciencePersistence(BaseTestCase):

    def setUp(self):
        self._service("start")
        super(TestConsciencePersistence, self).setUp()

    def _service(self, action, name=""):
        if name != "":
            name = "%s-%s" % (self.conf['namespace'], name)

        subprocess.check_call(['gridinit_cmd', '-S',
                    exp('~/.oio/sds/run/gridinit.sock'), action, name])

    def _start_cs(self, path, period, conf):
        cmd = "oio-daemon"
        opt="-O"
        path_opt = "PersistencePath="+exp(path)
        period_opt = "PersistencePeriod="+str(period)
        proc = subprocess.Popen([cmd, opt, path_opt, opt,
                                 period_opt, exp(conf)])
        return proc

    def _kill_and_watch_it_die(self, proc):
        try:
            proc.terminate()
        except Exception:
            pass
        proc.wait()

    def _register_services(self, score, srvtype):
        srv = self._srv(srvtype)
        srv['score'] = score
        self._register_srv(srv)

    def _check_score(self, score, srvtype):
        resp = self.request('GET', self._url_cs('list'),
                             params={"type":srvtype})
        body = self.json_loads(resp.data)
        self.assertIsInstance(body, list)
        self.assertEqual([score], [s['score'] for s in body])

    def test_conscience_persistence(self):
        self._service("stop")
        self._service('start', 'proxy')
        proc = self._start_cs('/tmp/pers', 1,
                             '~/.oio/sds/conf/OPENIO-conscience-1.conf')
        self._register_services(1, 'echo')
        self._check_score(1, 'echo')
        self._kill_and_watch_it_die(proc)
        time.sleep(2)
        proc = self._start_cs('/tmp/pers', 1,
                              '~/.oio/sds/conf/OPENIO-conscience-1.conf')
        self._check_score(1, 'echo')
        self._kill_and_watch_it_die(proc)

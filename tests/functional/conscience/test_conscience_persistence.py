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

import simplejson as json
import time
import subprocess
from tests.utils import CommonTestCase
from tests.utils import CODE_SRVTYPE_NOTMANAGED
from os.path import expanduser

def exp(path):
    return expanduser(path)


class TestConsciencePersistence(CommonTestCase):

    def _start_proxy(self, ip, ns):
        proc = subprocess.Popen(["oio-proxy", ip, ns])
        return proc

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
        self._flush_cs(srvtype)
        srv = self._srv(srvtype)
        srv['score'] = 1
        resp = self.request('POST', self._url_cs("lock"), json.dumps(srv))
        self.assertIn(resp.status, (200, 204))

    def _check_score(self, score, srvtype):
        resp = self.request('GET', self._url_cs('list'),
                             params={"type":srvtype})
        body = self.json_loads(resp.data)
        self.assertIsInstance(body, list)
        self.assertEqual([score], [s['score'] for s in body])

    def test_conscience_persistence(self):
        cs_ps = self._start_cs('/tmp/pers', 1,
                             '~/.oio/sds/conf/OPENIO-conscience-1.conf')
        px_ps = self._start_proxy('127.0.0.1:6000', 'OPENIO')
        time.sleep(0.1)

        self._register_services(1, 'echo')
        self._check_score(1, 'echo')

        self._kill_and_watch_it_die(cs_ps)
        cs_ps = self._start_cs('/tmp/pers', 1,
                              '~/.oio/sds/conf/OPENIO-conscience-1.conf')
        time.sleep(0.1)
        self._check_score(1, 'echo')

        self._kill_and_watch_it_die(cs_ps)
        self._kill_and_watch_it_die(px_ps)

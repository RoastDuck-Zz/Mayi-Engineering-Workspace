"""Native Linux core tests use only synthetic bytes and a pseudoterminal."""
import importlib.util
import json
import os
import pathlib
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = ROOT / 'native/l2_serial'
spec = importlib.util.spec_from_file_location('serial_fixtures', ROOT/'tests/fixtures/l2_serial/generate.py')
fixtures = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixtures)


class SerialSafety(unittest.TestCase):
    def test_no_device_command_path(self):
        sources = list(SRC.glob('*.cpp')) + list(SRC.glob('*.h'))
        self.assertGreaterEqual(len(sources), 9)
        runtime = '\n'.join(p.read_text() for p in sources)
        self.assertNotRegex(runtime, r'\b(setLidarWorkMode|resetLidar|syncLidarTimeStamp|SyncL2Clock|runParse)\s*\(')
        self.assertNotRegex(runtime, r'\b(write|writev|send|sendto|tcflow|tcsendbreak)\s*\(')
        self.assertNotIn('libunilidar', (ROOT/'scripts/build_l2_serial_monitor.sh').read_text())
        self.assertNotIn('O_RDWR', (SRC/'serial_transport.cpp').read_text())


@unittest.skipUnless(sys.platform.startswith('linux') and shutil.which('g++'), 'Linux g++ required; Ubuntu CI runs these tests')
class NativeSerial(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='guidedog-native-')
        cls.path = pathlib.Path(cls.temp.name)
        cls.exe = cls.path/'l2_serial_monitor'
        subprocess.run(['bash', str(ROOT/'scripts/build_l2_serial_monitor.sh'), str(cls.exe)], check=True)
        subprocess.run([sys.executable, str(ROOT/'tests/fixtures/l2_serial/generate.py'), str(cls.path)], check=True)
        cls.core = cls.path/'core-test'
        subprocess.run(['g++', '-std=c++17', '-Wall', '-Wextra', '-Werror', '-I', str(SRC),
                        str(ROOT/'tests/l2_serial_core_test.cpp'),
                        *[str(SRC/n) for n in ('frame_assembler.cpp', 'l2_packet_decoder.cpp', 'timestamp_analyzer.cpp')],
                        '-o', str(cls.core)], check=True)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_cpp_parser(self):
        subprocess.run([str(self.core), str(self.path)], check=True)

    def test_missing_device(self):
        p = subprocess.run([str(self.exe), '--device', str(self.path/'absent'),
                            '--output', str(self.path/'missing-device')], capture_output=True, text=True)
        self.assertNotEqual(p.returncode, 0)
        self.assertIn('persistent L2 device not found', p.stderr)
        self.assertIn('l2_serial_discover.sh', p.stderr)
        self.assertEqual(json.loads((self.path/'missing-device-summary.json').read_text())['status'], 'ERROR')

    def test_invalid_cli(self):
        for args in (['--seconds', 'nan'], ['--seconds', '-1'], ['--seconds', '1oops'],
                     ['--time-scale-den', '0'], ['--baudrate', '9600'], ['--unknown'], ['--device']):
            with self.subTest(args=args):
                p = subprocess.run([str(self.exe), *args], capture_output=True)
                self.assertEqual(p.returncode, 2)

    def run_pty(self, payload=None, stop_signal=None, disconnect=False):
        import pty
        import select
        import termios
        master, slave = pty.openpty()
        prefix = self.path/('run-'+str(time.monotonic_ns()))
        p = subprocess.Popen([str(self.exe), '--device', os.ttyname(slave), '--seconds', '.6',
                              '--output', str(prefix), '--frames-csv', '--sample-cloud-frame'],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            # Wait for transport configured, not an arbitrary startup sleep.
            end=time.monotonic()+3
            while time.monotonic()<end:
                attrs=termios.tcgetattr(slave)
                if not attrs[3]&termios.ICANON: break
                if p.poll() is not None: self.fail(p.communicate())
                time.sleep(.01)
            else: self.fail('transport did not configure PTY')
            self.assertFalse(attrs[3] & (termios.ECHO|termios.ICANON))
            self.assertFalse(attrs[0] & (termios.IXON|termios.IXOFF|termios.IXANY))
            self.assertFalse(attrs[2] & (termios.PARENB|termios.CSTOPB|termios.CRTSCTS|termios.HUPCL))
            self.assertEqual(attrs[2]&termios.CSIZE, termios.CS8)
            self.assertEqual(attrs[4],termios.B4000000)
            if payload:
                os.write(master,payload[:2]); time.sleep(.02)
                os.write(master,payload[2:])
                time.sleep(.08)
            if stop_signal: p.send_signal(stop_signal)
            if disconnect: os.close(master); master=-1
            stdout,stderr=p.communicate(timeout=4)
            if master!=-1:
                self.assertFalse(select.select([master],[],[],0)[0], 'monitor transmitted bytes')
            summary=json.loads(pathlib.Path(str(prefix)+'-summary.json').read_text())
            self.assertEqual(summary['safe_device_writes'], {'work_mode_write':False,'time_sync_write':False,'reset':False})
            self.assertTrue(summary['clean_exit'])
            return p.returncode,summary,prefix,stderr
        finally:
            if p.poll() is None: p.kill(); p.wait()
            if master!=-1: os.close(master)
            os.close(slave)

    def test_stream_report(self):
        code,s,prefix,_=self.run_pty(fixtures.imu()+fixtures.cloud()+fixtures.packet(999,b'abcd'))
        self.assertEqual(code,0)
        self.assertEqual((s['imu_frames'],s['cloud_frames'],s['unknown_frames']),(1,1,1))
        self.assertEqual(s['point_stats']['points_total'],2)
        self.assertAlmostEqual(s['point_stats']['y_min'],1,places=6)
        self.assertIsNone(s['imu_timestamp']['host_ratio'])
        self.assertEqual(s['imu_timestamp']['first_raw'],10.25)
        self.assertEqual(len(pathlib.Path(str(prefix)+'-sample-cloud.csv').read_text().splitlines()),3)
        self.assertIn('header_valid',pathlib.Path(str(prefix)+'-frames.csv').read_text())

    def test_no_data_is_not_success(self):
        code,s,_,_=self.run_pty()
        self.assertEqual(code,3)
        self.assertEqual(s['status'],'NO_DATA')
        self.assertIsNone(s['point_stats']['x_min'])
        self.assertIsNone(s['cloud_timestamp']['delta'])

    def test_signal_shutdown(self):
        code,s,_,_=self.run_pty(fixtures.imu(),signal.SIGTERM)
        self.assertEqual(code,128+signal.SIGTERM)
        self.assertEqual(s['status'],'INTERRUPTED')

    def test_disconnect_propagates_failure(self):
        code,s,_,_=self.run_pty(fixtures.imu(),disconnect=True)
        self.assertEqual(code,1)
        self.assertEqual(s['status'],'ERROR')


if __name__ == '__main__': unittest.main()

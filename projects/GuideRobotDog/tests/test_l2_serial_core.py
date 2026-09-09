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

    def test_read_size_cli(self):
        for value in ('0','64','2048','999999','8192x'):
            p=subprocess.run([str(self.exe),'--read-size',value],capture_output=True)
            self.assertEqual(p.returncode,2)
        for value in ('1024','4096','8192','16384','32768'):
            prefix=self.path/('size-'+value)
            p=subprocess.run([str(self.exe),'--read-size',value,'--device',str(self.path/'absent'),
                              '--output',str(prefix)],capture_output=True)
            self.assertEqual(p.returncode,1)

    def test_replay_and_capture_limits(self):
        subprocess.run(['bash',str(ROOT/'scripts/build_l2_serial_integrity.sh'),str(self.path)],check=True)
        capture=self.path/'l2_serial_capture';replay=self.path/'l2_serial_replay'
        for args in (['--seconds','11'],['--seconds','nan'],['--seconds','0'],['--max-bytes','16777217']):
            p=subprocess.run([str(capture),*args,'--output',str(self.path/'never.bin')],capture_output=True)
            self.assertEqual(p.returncode,2)
        raw=self.path/'same.bin';raw.write_bytes(fixtures.imu()+fixtures.cloud()+fixtures.imu(seq=9))
        out=self.path/'replay.json'
        subprocess.run([str(replay),'--input',str(raw),'--output',str(out)],check=True)
        cpp=json.loads(out.read_text())
        py_path=self.path/'python.json'
        subprocess.run([sys.executable,str(ROOT/'scripts/l2_raw_stream_check.py'),str(raw),'--output',str(py_path)],check=True)
        py=json.loads(py_path.read_text())
        for key in ('bytes_received','valid_frames','crc_errors','cloud_frames','imu_frames','imu_sequence','cloud_sequence'):
            self.assertEqual(cpp[key],py[key],key)
        self.assertIsNone(cpp['imu_timestamp']['host_ratio'])
        import struct,zlib
        malformed=[]
        for frame,offset,value in ((fixtures.imu(),24,1000000000),(fixtures.cloud(),128,301)):
            b=bytearray(frame);struct.pack_into('<I',b,offset,value)
            struct.pack_into('<I',b,len(b)-12,zlib.crc32(b[12:-12]));malformed.append(b)
        badraw=self.path/'malformed.bin'
        badraw.write_bytes(b''.join(malformed)+b'xxxxxxxx'+bytes.fromhex('55aa050a'))
        badcpp=self.path/'malformed-cpp.json';badpy=self.path/'malformed-py.json'
        subprocess.run([str(replay),'--input',str(badraw),'--output',str(badcpp)],check=True)
        subprocess.run([sys.executable,str(ROOT/'scripts/l2_raw_stream_check.py'),str(badraw),'--output',str(badpy)],check=True)
        a=json.loads(badcpp.read_text());b=json.loads(badpy.read_text())
        for key in ('valid_frames','decode_errors','cloud_frames','imu_frames','cloud_sequence','imu_sequence','trailing_bytes'):
            self.assertEqual(a[key],b[key],key)
        self.assertEqual(a['decode_errors'],2)
        large=self.path/'large.bin'
        with large.open('wb') as f:f.truncate(16*1024*1024+1)
        result=subprocess.run([str(replay),'--input',str(large),'--output',str(self.path/'large.json')],capture_output=True)
        self.assertNotEqual(result.returncode,0)
        self.assertFalse((self.path/'large.json').exists())
        original=raw.read_bytes()
        alias=self.path/'alias.bin';alias.symlink_to(raw)
        hard=self.path/'hard.bin';os.link(raw,hard)
        for target in (alias,hard,out):
            before=target.read_bytes()
            for command in ([str(replay),'--input',str(raw),'--output',str(target)],
                            [sys.executable,str(ROOT/'scripts/l2_raw_stream_check.py'),str(raw),'--output',str(target)]):
                result=subprocess.run(command,capture_output=True)
                self.assertNotEqual(result.returncode,0)
                self.assertEqual(target.read_bytes(),before)
                self.assertEqual(raw.read_bytes(),original)
        # Hard byte cap checked with an actual PTY producer, never a real device.
        import pty,tty
        master,slave=pty.openpty();tty.setraw(slave)
        dest=self.path/'bounded.bin'
        p=subprocess.Popen([str(capture),'--device',os.ttyname(slave),'--seconds','.3',
                            '--max-bytes','64','--output',str(dest)],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        try:
            end=time.monotonic()+2
            while not dest.exists() and time.monotonic()<end:time.sleep(.01)
            time.sleep(.05);os.write(master,fixtures.imu())
            stdout,stderr=p.communicate(timeout=3)
            self.assertEqual(p.returncode,0,(stdout,stderr));self.assertEqual(dest.stat().st_size,64)
            again=subprocess.run([str(capture),'--output',str(dest)],capture_output=True)
            self.assertNotEqual(again.returncode,0);self.assertEqual(dest.stat().st_size,64)
        finally:
            if p.poll() is None:p.kill();p.wait()
            os.close(master);os.close(slave)

    def test_discards_preopen_backlog(self):
        import pty
        import tty
        master,slave=pty.openpty()
        prefix=self.path/'stale-backlog'
        try:
            tty.setraw(slave)
            os.write(master,fixtures.imu(sec=1))
            time.sleep(.02)
            p=subprocess.run([str(self.exe),'--device',os.ttyname(slave),
                              '--seconds','.2','--output',str(prefix)],capture_output=True,timeout=4)
            summary=json.loads(pathlib.Path(str(prefix)+'-summary.json').read_text())
            self.assertEqual(p.returncode,3)
            self.assertEqual(summary['imu_frames'],0)
            self.assertIsNone(summary['imu_timestamp']['first_raw'])
        finally:
            os.close(master);os.close(slave)

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

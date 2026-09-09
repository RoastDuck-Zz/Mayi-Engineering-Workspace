import importlib.util
import json
import pathlib
import struct
import tempfile
import unittest
import zlib

ROOT=pathlib.Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('fixtures',ROOT/'tests/fixtures/l2_serial/generate.py');fixtures=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixtures)
raw_spec=importlib.util.spec_from_file_location('raw',ROOT/'scripts/l2_udp_raw_check.py');raw=importlib.util.module_from_spec(raw_spec);raw_spec.loader.exec_module(raw)

def capture(frames):
    out=bytearray(b'GDL2UDP1')
    for i,payload in enumerate(frames):
        out+=struct.pack('<QH4sI',1_000_000_000+i*10_000_000,6101,bytes([192,168,1,62]),len(payload))+payload
    return bytes(out)

class UdpCoreTests(unittest.TestCase):
    def test_modulo_sequence_and_timestamp_gap(self):
        self.assertEqual(raw.seq_stats([1022,1023,0,1])['wraps'],1)
        s=raw.seq_stats([1022,1]);self.assertEqual(s['estimated_missing_between_valid_frames'],2)
        s=raw.seq_stats([105,103]);self.assertEqual(s['backward_unexpected'],1);self.assertEqual(s['estimated_missing_between_valid_frames'],0)
        s=raw.seq_stats([100,102,101,103]);self.assertEqual(s['forward_gaps'],1);self.assertEqual(s['late_packet_count'],1)

    def test_raw_capture_checks_crc_and_datagram_records(self):
        with tempfile.TemporaryDirectory() as d:
            path=pathlib.Path(d)/'sample.udpbin';path.write_bytes(capture([fixtures.imu(),fixtures.cloud(),fixtures.imu(seq=8)]))
            result=raw.analyze(path)
            self.assertEqual(result['datagrams_total'],3);self.assertEqual(result['cloud_frames'],1);self.assertEqual(result['imu_frames'],2);self.assertEqual(result['crc_errors'],0)

    def test_bad_crc_and_source_contract(self):
        source=(ROOT/'native/l2_ethernet/l2_udp_monitor.cpp').read_text()
        self.assertIn('recvmsg(',source);self.assertIn('SO_RXQ_OVFL',source)
        self.assertNotIn('sendto(',source);self.assertNotIn('runParse(',source);self.assertNotIn('setLidarWorkMode(',source)
        bad=bytearray(fixtures.imu());bad[30]^=1
        with tempfile.TemporaryDirectory() as d:
            p=pathlib.Path(d)/'bad.udpbin';p.write_bytes(capture([bytes(bad)]));self.assertEqual(raw.analyze(p)['crc_errors'],1)

    def test_host_stats_is_read_only_and_explicit(self):
        text=(ROOT/'scripts/l2_udp_host_stats.py').read_text()
        self.assertNotIn('open(',text.replace('path.open(','').replace("pathlib.Path('/proc/net/snmp').read_text()",''))
        self.assertIn('RcvbufErrors',text)

    def test_mount_probe_is_observation_only(self):
        spec=importlib.util.spec_from_file_location('mount',ROOT/'scripts/l2_mount_probe.py');mount=importlib.util.module_from_spec(spec);spec.loader.exec_module(mount)
        with tempfile.TemporaryDirectory() as d:
            p=pathlib.Path(d)/'points.csv';p.write_text('x,y,z\n0.1,2.0,0.2\n',encoding='utf-8')
            r=mount.probe(p);self.assertEqual(r['axis'],'+Y_lidar');self.assertFalse(r['tf_written'])

if __name__=='__main__':unittest.main()

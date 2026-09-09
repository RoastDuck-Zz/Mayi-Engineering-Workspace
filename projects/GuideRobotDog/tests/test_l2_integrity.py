import importlib.util
import pathlib
import struct
import unittest
import zlib
import tempfile

ROOT=pathlib.Path(__file__).resolve().parents[1]


def load(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/'scripts'/f'{name}.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


def packet(kind,seq=0,length=80):
    p=bytearray(length-24);struct.pack_into('<IIII',p,0,seq,len(p),10,0)
    return bytes.fromhex('55aa050a')+struct.pack('<II',kind,length)+p+struct.pack('<II',zlib.crc32(p),0)+bytes.fromhex('000000ff')


class IntegrityTests(unittest.TestCase):
    def test_truncated_header_after_noise(self):
        m=load('l2_raw_stream_check')
        r=m.analyze(b'xxxxxxxx'+m.MAGIC)
        self.assertEqual(r['valid_frames'],0)
        self.assertEqual(r['trailing_bytes'],4)

    def test_invalid_payload_excluded_from_decoded_counts(self):
        m=load('l2_raw_stream_check')
        frames=[]
        for kind,size,offset,value in [(104,80,24,1000000000),(102,1044,128,301)]:
            b=bytearray(packet(kind,1,size));struct.pack_into('<I',b,offset,value)
            struct.pack_into('<I',b,size-12,zlib.crc32(b[12:-12]));frames.append(b)
        r=m.analyze(b''.join(frames))
        self.assertEqual(r['valid_frames'],2)
        self.assertEqual(r['decode_errors'],2)
        self.assertEqual(r['cloud_frames']+r['imu_frames'],0)

    def test_checker_present(self):
        self.assertTrue((ROOT/'scripts/l2_raw_stream_check.py').exists())

    def test_wrap_gap_duplicates(self):
        m=load('l2_raw_stream_check')
        r=m.analyze(b''.join(packet(104,n) for n in [1022,1023,0,2,2,1]))
        s=r['imu_sequence']
        self.assertEqual(s['wraps'],1);self.assertEqual(s['duplicates'],1)
        self.assertEqual(s['estimated_missing_between_valid_frames'],1)
        self.assertEqual(s['backward_unexpected'],1)
        self.assertEqual(s['expected_next'],2)
        self.assertEqual(s['confirmed_packet_loss'],'UNKNOWN')

    def test_gap_histogram(self):
        m=load('l2_raw_stream_check')
        cloud=packet(102,1,1044);short=cloud[:200]+cloud[264:]
        r=m.analyze(short+packet(104,2)+packet(104,3))
        self.assertEqual(r['gap_size_histogram']['64'],1)
        self.assertEqual(r['imu_frames'],2);self.assertEqual(r['cloud_frames'],0)

    def test_corrupt_crc_dropped(self):
        m=load('l2_raw_stream_check');b=bytearray(packet(104));b[30]^=1
        r=m.analyze(bytes(b)+packet(104,1))
        self.assertEqual(r['crc_errors'],1);self.assertEqual(r['valid_frames'],1)

    def test_tty_unsupported_not_zero(self):
        m=load('l2_tty_stats')
        def fail(*args): raise OSError(25,'unsupported')
        r=m.read_counters(1,fail)
        self.assertEqual(r['status'],'UNSUPPORTED');self.assertIsNone(r['counters'])
        self.assertIsNone(m.delta(r,r))

    def test_tty_delta(self):
        m=load('l2_tty_stats')
        a={'status':'SUPPORTED','counters':{'rx':10,'tx':0,'overrun':1}}
        b={'status':'SUPPORTED','counters':{'rx':20,'tx':0,'overrun':3}}
        self.assertEqual(m.delta(a,b),{'rx':10,'tx':0,'overrun':2})

    def test_usb_default_redaction(self):
        m=load('l2_usb_diagnostics')
        with tempfile.TemporaryDirectory() as temp:
            usb=pathlib.Path(temp)/'usb-private-path';interface=usb/'interface0';interface.mkdir(parents=True)
            for name,value in {'idVendor':'1a86','idProduct':'55d3','serial':'PRIVATE-SERIAL','speed':'12','bDeviceClass':'02'}.items():
                (usb/name).write_text(value)
            r=m.describe(interface,False)
            self.assertEqual(r['speed_mbps'],'12')
            self.assertNotIn('PRIVATE-SERIAL',str(r));self.assertNotIn(temp,str(r))


if __name__=='__main__': unittest.main()

import importlib.util
import pathlib
import struct
import unittest
import zlib

ROOT=pathlib.Path(__file__).resolve().parents[1]


def packet(kind,payload):
    return bytes.fromhex('55aa050a')+struct.pack('<II',kind,len(payload)+24)+payload+struct.pack('<II',zlib.crc32(payload),0)+bytes.fromhex('000000ff')


class ModeOnceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path=ROOT/'scripts/l2_transport_mode_once.py'
        if not path.exists(): return
        spec=importlib.util.spec_from_file_location('mode_once',path)
        cls.m=importlib.util.module_from_spec(spec);spec.loader.exec_module(cls.m)

    def test_tool_exists(self):
        self.assertTrue((ROOT/'scripts/l2_transport_mode_once.py').is_file())

    def test_protocol_allowlist(self):
        if not hasattr(self,'m'): self.skipTest('tool missing')
        self.assertEqual(self.m.QUERY,packet(100,struct.pack('<II',6,0)))
        self.assertEqual(self.m.SET8,packet(2002,struct.pack('<I',8)))
        self.assertEqual(self.m.RESET,packet(100,struct.pack('<II',1,1)))

    def run_flow(self,responses,activate=True,reset=False):
        sent=[]
        class Fake:
            def send(inner,b): sent.append(b)
            def receive_mode(inner): return responses.pop(0)
        result=self.m.execute(Fake(),activate,reset)
        return result,sent

    def test_already_eight_never_sets_or_resets(self):
        if not hasattr(self,'m'): self.skipTest('tool missing')
        result,sent=self.run_flow([8])
        self.assertEqual(sent,[self.m.QUERY]);self.assertEqual(result['before'],8)

    def test_unknown_mode_no_write(self):
        if not hasattr(self,'m'): self.skipTest('tool missing')
        result,sent=self.run_flow([None])
        self.assertEqual(sent,[self.m.QUERY]);self.assertFalse(result['success'])

    def test_query_only(self):
        if not hasattr(self,'m'): self.skipTest('tool missing')
        result,sent=self.run_flow([0],False)
        self.assertEqual(sent,[self.m.QUERY]);self.assertTrue(result['success'])

    def test_set_once_verify_then_reset_once(self):
        if not hasattr(self,'m'): self.skipTest('tool missing')
        result,sent=self.run_flow([0,8],reset=True)
        self.assertEqual(sent,[self.m.QUERY,self.m.SET8,self.m.QUERY,self.m.RESET])
        self.assertEqual(result['after'],8);self.assertTrue(result['reset_sent'])

    def test_default_activation_does_not_reset(self):
        result,sent=self.run_flow([0,8])
        self.assertEqual(sent,[self.m.QUERY,self.m.SET8,self.m.QUERY])
        self.assertTrue(result['success']);self.assertFalse(result['reset_sent'])

    def test_partial_write_attempt_cannot_repeat(self):
        c=self.m.Connection.__new__(self.m.Connection)
        c.sent=[];c.peer=('fixture',6101)
        class FakeSocket:
            def sendto(inner,b,peer): return 1
        c.sock=FakeSocket()
        with self.assertRaisesRegex(RuntimeError,'partial'): c.send(self.m.SET8)
        with self.assertRaisesRegex(RuntimeError,'once'): c.send(self.m.SET8)
        self.assertEqual(c.sent,[self.m.SET8])

    def test_unverified_set_not_retried_or_reset(self):
        if not hasattr(self,'m'): self.skipTest('tool missing')
        result,sent=self.run_flow([0,None])
        self.assertEqual(sent,[self.m.QUERY,self.m.SET8,self.m.QUERY])
        self.assertFalse(result['success']);self.assertFalse(result['reset_sent'])

    def test_parse_validated_mode_only(self):
        if not hasattr(self,'m'): self.skipTest('tool missing')
        b=packet(107,struct.pack('<I',8));self.assertEqual(self.m.mode_from_frame(b),8)
        for bad in (b[:-1],b[:12]+b'xxxx'+b[16:],packet(106,struct.pack('<II',8,0))):
            self.assertIsNone(self.m.mode_from_frame(bad))

    def test_acceptance_fields_separate(self):
        config=(ROOT/'config/l2.yaml').read_text(encoding='utf-8')
        self.assertIn('descriptor_close_no_data:',config)
        self.assertIn('streaming_clean_shutdown:',config)
        self.assertNotIn('\n  clean_shutdown:',config)


if __name__=='__main__': unittest.main()

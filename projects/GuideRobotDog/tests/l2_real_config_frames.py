"""Regression check against saved REAL multi-frame responses, never synthetic LiDAR."""
import json,pathlib,sys
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'scripts'))
from l2_wire_analyzer import frames
records=json.loads(pathlib.Path(sys.argv[1]).read_text())
received=[r for r in records if r['direction']=='received']
decoded=[f for r in received for f in frames(bytes.fromhex(r['hex']))]
assert all('error' not in f and f['crc_ok'] and f['tail_ok'] for f in decoded)
assert any(f['type']==101 for f in decoded), 'embedded ACK was missed'
assert any(f.get('work_mode')==int(sys.argv[2]) for f in decoded), 'mode response not decoded'
assert len(decoded)>len(received), 'expected real concatenated datagrams'
print('PASS: saved real concatenated frames, CRC, ACK and mode readback')

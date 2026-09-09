"""Read-only legacy parameter/version queries verified in the fixed SDK disassembly.
No parameter set/save/reset commands. Retains every control response verbatim.
"""
import socket, struct, time, zlib, json, pathlib, sys
out=pathlib.Path(sys.argv[1]); out.mkdir(parents=True,exist_ok=True)
s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
s.bind(('192.168.1.2',6201)); s.settimeout(0.2)
records=[]
# sendRequestOfLidarParam constructs type=2000, cmd=3, value=3, length=32.
# Version GET is command 4 per public protocol; query both versions of public API.
for typ,cmd,value in [(2000,3,3),(2000,4,0),(100,6,0),(100,3,0)]:
    payload=struct.pack('<II',cmd,value)
    packet=bytes.fromhex('55aa050a')+struct.pack('<II',typ,32)+payload+struct.pack('<II',zlib.crc32(payload),0)+bytes.fromhex('000000ff')
    records.append(dict(direction='sent',type=typ,cmd=cmd,value=value,hex=packet.hex()))
    s.sendto(packet,('192.168.1.62',6101))
    end=time.monotonic()+2
    while time.monotonic()<end:
        try: b,peer=s.recvfrom(65535)
        except socket.timeout: continue
        if peer!=('192.168.1.62',6101) or len(b)<24: continue
        t=struct.unpack_from('<I',b,4)[0]
        if t not in (102,104):
            rec=dict(direction='received',type=t,length=len(b),hex=b.hex(),crc_ok=zlib.crc32(b[12:-12])==struct.unpack_from('<I',b,len(b)-12)[0])
            records.append(rec)
s.close()
(out/'config-query.json').write_text(json.dumps(records,indent=2))
print(json.dumps(records,indent=2))

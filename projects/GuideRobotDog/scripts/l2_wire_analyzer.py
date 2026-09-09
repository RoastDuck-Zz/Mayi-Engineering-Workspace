"""Offline PCAP or bounded live UDP analysis. Never sends commands or adjusts time."""
import argparse, collections, csv, json, math, pathlib, socket, statistics, struct, time, zlib

MAGIC=bytes.fromhex('55aa050a')
def frames(data):
    offset=0
    while offset<len(data):
        if len(data)-offset<24 or data[offset:offset+4]!=MAGIC:
            yield dict(error='invalid_header_or_trailing_bytes',offset=offset); return
        typ,size=struct.unpack_from('<II',data,offset+4)
        if size<24 or offset+size>len(data):
            yield dict(error='invalid_frame_length',offset=offset,type=typ,size=size); return
        b=data[offset:offset+size]; payload=b[12:-12]
        f=dict(type=typ,size=size,offset=offset,crc_ok=zlib.crc32(payload)==struct.unpack_from('<I',b,size-12)[0],tail_ok=b[-2:]==bytes.fromhex('00ff'))
        if typ in (102,104) and len(payload)>=16:
            seq,pl,sec,ns=struct.unpack_from('<IIII',payload)
            f.update(sequence=seq,payload_size=pl,sec=sec,nsec=ns,device_ns=sec*10**9+ns)
            if typ==104 and len(payload)==56:
                values=struct.unpack_from('<10f',payload,16)
                f.update(imu_values=list(values),imu_finite=all(map(math.isfinite,values)))
        else:
            f['hex']=b.hex()
            if typ==107 and len(payload)==4: f['work_mode']=struct.unpack('<I',payload)[0]
        yield f
        offset+=size

def pcap(path):
    with open(path,'rb') as s:
        h=s.read(24)
        if h[:4]!=bytes.fromhex('d4c3b2a1') or struct.unpack_from('<I',h,20)[0]!=1:
            raise ValueError('requires little-endian microsecond Ethernet PCAP')
        while h:=s.read(16):
            sec,us,n,original=struct.unpack('<IIII',h); b=s.read(n)
            if len(b)<14: continue
            et=struct.unpack_from('!H',b,12)[0]; ip=14
            while et in (0x8100,0x88a8): et=struct.unpack_from('!H',b,ip+2)[0]; ip+=4
            if et!=0x0800 or len(b)<ip+20 or b[ip+9]!=17: continue
            frag=struct.unpack_from('!H',b,ip+6)[0]
            if frag&0x3fff: raise ValueError('fragmented UDP requires reassembly; not silently counted')
            udp=ip+(b[ip]&15)*4; sp,dp,length=struct.unpack_from('!HHH',b,udp)
            if udp+length>len(b): raise ValueError('truncated datagram: use tcpdump -s 0')
            yield None,sec+us*1e-6,socket.inet_ntoa(b[ip+12:ip+16]),sp,socket.inet_ntoa(b[ip+16:ip+20]),dp,b[udp+8:udp+length]

def live(host,lidar,seconds):
    with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as s:
        s.bind((host,6201)); s.settimeout(.2); deadline=time.monotonic()+seconds
        while time.monotonic()<deadline:
            try: b,peer=s.recvfrom(65535)
            except socket.timeout: continue
            mono=time.monotonic(); real=time.time()
            if peer[0]==lidar: yield mono,real,peer[0],peer[1],host,6201,b

def analyze(stream,prefix):
    lengths=collections.Counter(); types=collections.Counter(); routes=collections.Counter(); sizes=collections.Counter()
    samples=collections.defaultdict(list); control=[]; malformed=crc_bad=tail_bad=imu_invalid=0; datagrams=0
    p=pathlib.Path(prefix); p.parent.mkdir(parents=True,exist_ok=True)
    with open(str(p)+'-frames.csv','w',newline='') as out:
        w=csv.writer(out); w.writerow(['host_monotonic','host_realtime','type','sequence','device_sec_raw','device_nsec_raw','frame_size','crc_ok'])
        for mono,real,src,sp,dst,dp,data in stream:
            datagrams+=1;lengths[len(data)]+=1;routes[f'{src}:{sp}->{dst}:{dp}']+=1
            for f in frames(data):
                if 'error' in f: malformed+=1;control.append(f);continue
                t=f['type'];types[t]+=1;sizes[f'{t}:{f["size"]}']+=1
                crc_bad+=not f['crc_ok'];tail_bad+=not f['tail_ok']
                w.writerow([mono,real,t,f.get('sequence'),f.get('sec'),f.get('nsec'),f['size'],f['crc_ok']])
                if 'sequence' in f:
                    samples[t].append((mono if mono is not None else real,f['device_ns'],f['sequence'],f['nsec']))
                    if t==104 and not f.get('imu_finite',False):imu_invalid+=1
                elif len(control)<1000:control.append(f)
    result=dict(datagrams=datagrams,udp_lengths=dict(lengths),message_types=dict(types),frame_sizes=dict(sizes),ports=dict(routes),malformed=malformed,crc_errors=crc_bad,tail_errors=tail_bad,imu_invalid=imu_invalid,outbound_commands=0,control_frames=control,streams={})
    for typ,rows in samples.items():
        windows=[]; anchor=rows[0]
        # Observed firmware counter: exact 1023->0 transitions, NOT uint32 overflow.
        # This is an observed rollover, not proof that any skipped position was a lost UDP packet.
        modulus=1024 if max(r[2] for r in rows)==1023 and any(a[2]==1023 and b[2]==0 for a,b in zip(rows,rows[1:])) else None
        forward=back=wrap=duplicates=0
        for a,b in zip(rows,rows[1:]):
            if b[2]==a[2]:duplicates+=1
            elif b[2]<a[2]:
                if modulus and a[2]==modulus-1 and b[2]==0:wrap+=1
                else:back+=1
            elif b[2]!=a[2]+1:forward+=1
            if b[0]-anchor[0]>=10:
                delta=(b[1]-anchor[1])/1e9; elapsed=b[0]-anchor[0]
                windows.append(dict(host_delta=elapsed,device_delta=delta,ratio=delta/elapsed))
                anchor=b
        ratios=[x['ratio'] for x in windows]
        result['streams'][typ]=dict(count=len(rows),windows=windows,
            ratio_mean=statistics.mean(ratios) if ratios else None,
            ratio_std=statistics.pstdev(ratios) if ratios else None,
            ratio_min=min(ratios) if ratios else None,ratio_max=max(ratios) if ratios else None,
            confirmed_packet_loss='UNKNOWN',unknown_sequence_discontinuity=forward+back+duplicates,
            sequence_reset='UNKNOWN',sequence_wrap=wrap if modulus else 'UNKNOWN',observed_modulus=modulus,
            reset_or_unobserved_wrap_candidates=back,
            forward_gap_events=forward,duplicate_events=duplicates,
            nsec_out_of_range=sum(not 0<=r[3]<10**9 for r in rows),
            device_time_backsteps=sum(b[1]<a[1] for a,b in zip(rows,rows[1:])),
            max_receive_gap=max((b[0]-a[0] for a,b in zip(rows,rows[1:])),default=0))
    with open(str(p)+'-summary.json','w') as s:json.dump(result,s,indent=2)
    return result

if __name__=='__main__':
    ap=argparse.ArgumentParser();g=ap.add_mutually_exclusive_group(required=True)
    g.add_argument('--pcap');g.add_argument('--live',type=float)
    ap.add_argument('--host',default='192.168.1.2');ap.add_argument('--lidar',default='192.168.1.62');ap.add_argument('--output',required=True)
    a=ap.parse_args()
    if a.live is not None and not 1<=a.live<=120:ap.error('live duration must be 1..120 seconds')
    result=analyze(pcap(a.pcap) if a.pcap else live(a.host,a.lidar,a.live),a.output)
    print(json.dumps(result,indent=2))

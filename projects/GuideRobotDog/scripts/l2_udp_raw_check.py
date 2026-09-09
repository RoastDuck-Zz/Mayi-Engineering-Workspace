"""Independent bounded GDL2UDP1 analyzer using struct/zlib only."""
import argparse, json, pathlib, struct, statistics, zlib
MAGIC=b'GDL2UDP1'; FRAME=b'\x55\xaa\x05\x0a'; LIMIT=16*1024*1024

def seq_stats(values):
    out={'first_seq':None,'last_seq':None,'frames':0,'duplicates':0,'forward_gaps':0,'estimated_missing_between_valid_frames':0,'backward_unexpected':0,'wraps':0,'immediate_gap_events':0,'late_packet_count':0,'reorder_events':0,'unrecovered_missing_after_window':0}
    prev=None;seen=set();pending=set()
    for v in values:
        if out['first_seq'] is None:out['first_seq']=v
        if v in pending:
            pending.remove(v);out['late_packet_count']+=1;out['reorder_events']+=1
        elif v in seen:out['duplicates']+=1
        elif prev is not None:
            d=(v-prev)%1024
            if d==1:
                if prev==1023 and v==0:out['wraps']+=1
                prev=v
            elif d<=512:
                out['forward_gaps']+=1;out['immediate_gap_events']+=1;out['estimated_missing_between_valid_frames']+=d-1
                pending.update((prev+i)%1024 for i in range(1,d));prev=v
            else:out['backward_unexpected']+=1;out['late_packet_count']+=1;out['reorder_events']+=1
        else:prev=v
        seen.add(v);out['frames']+=1;out['last_seq']=v
    out['unrecovered_missing_after_window']=len(pending);out['expected_next']=(prev+1)%1024 if prev is not None else None;out['sequence_gap_observed']=bool(out['forward_gaps'] or out['backward_unexpected']);out['confirmed_packet_loss']='UNKNOWN';return out

def frame(data, offset):
    if len(data)-offset<12 or data[offset:offset+4]!=FRAME:return None,offset,'malformed_header'
    typ,size=struct.unpack_from('<II',data,offset+4)
    if size<24 or size>65536 or offset+size>len(data):return None,offset,'size_mismatch'
    b=data[offset:offset+size]
    if b[-2:]!=b'\x00\xff':return None,offset+size,'tail'
    if zlib.crc32(b[12:-12])!=struct.unpack_from('<I',b,size-12)[0]:return None,offset+size,'crc'
    return (typ,b),offset+size,None

def analyze(path):
    raw=pathlib.Path(path).read_bytes()
    if len(raw)>LIMIT or raw[:8]!=MAGIC:raise ValueError('invalid capture')
    p=8;result={'bytes':len(raw),'datagrams_total':0,'crc_errors':0,'tail_errors':0,'malformed_header':0,'size_mismatch':0,'cloud_frames':0,'imu_frames':0,'unknown_types':0,'cloud':{},'imu':{}}
    streams={102:[] ,104:[]}
    while p<len(raw):
        if p+18>len(raw):raise ValueError('truncated record')
        arrival,port,ip,n=struct.unpack_from('<QH4sI',raw,p);p+=18
        if n>65536 or p+n>len(raw):raise ValueError('invalid datagram record')
        datagram=raw[p:p+n];p+=n;result['datagrams_total']+=1;offset=0
        while offset<len(datagram):
            parsed,next_offset,error=frame(datagram,offset)
            if error:result[{'crc':'crc_errors','tail':'tail_errors'}.get(error,error)]+=1;break
            typ,b=parsed
            if typ not in (102,104):result['unknown_types']+=1
            else:
                seq,_,sec,nsec=struct.unpack_from('<IIII',b,12)
                if nsec>=1000000000:continue
                result['cloud_frames' if typ==102 else 'imu_frames']+=1;streams[typ].append((seq,sec+nsec/1e9,arrival/1e9))
            offset=next_offset
    for typ,rows in streams.items():
        vals=[x[0] for x in rows];raw_period=[];host_period=[];gaps=[]
        for a,b in zip(rows,rows[1:]):
            d=(b[0]-a[0])%1024
            if d==1:raw_period.append(b[1]-a[1]);host_period.append(b[2]-a[2])
            elif d:
                nominal=statistics.median(raw_period) if len(raw_period)>=30 else None
                ratio=(b[1]-a[1])/(d*nominal) if nominal and d>0 and b[1]>a[1] else None
                gaps.append({'previous_seq':a[0],'current_seq':b[0],'mod_delta':d,'raw_timestamp_delta':b[1]-a[1],'host_delta':b[2]-a[2],'time_span_consistent':None if ratio is None else .8<=ratio<=1.2,'ratio':ratio})
        def summary(v):
            if not v:return {'count':0,'min':None,'median':None,'p50':None,'p95':None,'max':None}
            s=sorted(v);return {'count':len(v),'min':min(v),'median':statistics.median(s),'p50':statistics.median(s),'p95':s[min(len(s)-1,int(.95*(len(s)-1)))],'max':max(v)}
        result['cloud' if typ==102 else 'imu']={'sequence':seq_stats(vals),'nominal_period':{'raw_device_seconds':summary(raw_period),'host_seconds':summary(host_period)},'gap_observations':gaps[:64]}
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('input');p.add_argument('--output');a=p.parse_args();text=json.dumps(analyze(a.input),indent=2)
    if a.output:
        with pathlib.Path(a.output).open('x',encoding='utf-8') as output:output.write(text)
    else:print(text)

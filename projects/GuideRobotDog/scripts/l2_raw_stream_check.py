"""Independent bounded raw replay using struct/zlib. Never opens a serial device."""
import argparse
import collections
import json
import pathlib
import struct
import zlib

MAGIC=bytes.fromhex('55aa050a')
LIMIT=16*1024*1024
SIZES={100:32,101:40,102:1044,103:5536,104:80,105:104,106:32,107:28,108:44,109:32}


def sequence(values):
    r=dict(first_seq=None,last_seq=None,frames=0,expected_next=None,duplicates=0,
           forward_gaps=0,estimated_missing_between_valid_frames=0,backward_unexpected=0,
           wraps=0,out_of_range=0,immediate_gap_events=0,late_packet_count=0,
           reorder_events=0,unrecovered_missing_after_window=0,
           sequence_gap_observed=False,confirmed_packet_loss='UNKNOWN')
    for v in values:
        prev=r['last_seq']
        if r['first_seq'] is None:r['first_seq']=v
        r['frames']+=1;r['last_seq']=v;r['expected_next']=(v+1)%1024 if v<1024 else None
        if v>=1024:r['out_of_range']+=1
        if prev is None:continue
        if v==prev:r['duplicates']+=1
        elif v<1024 and prev<1024:
            delta=(v-prev)%1024
            if delta==1:
                if prev==1023 and v==0:r['wraps']+=1
            elif delta<=512:
                r['forward_gaps']+=1;r['immediate_gap_events']+=1;r['estimated_missing_between_valid_frames']+=delta-1
            else:r['backward_unexpected']+=1;r['late_packet_count']+=1;r['reorder_events']+=1
        elif v<prev:r['backward_unexpected']+=1;r['late_packet_count']+=1;r['reorder_events']+=1
    r['sequence_gap_observed']=bool(r['forward_gaps'] or r['backward_unexpected'])
    return r


def analyze(data):
    if len(data)>LIMIT:raise ValueError('raw capture exceeds 16 MiB')
    p=0;valid=[];bad=[];crc=tail=discarded=decode_errors=0
    while p+12<=len(data):
        k=data.find(MAGIC,p)
        if k<0:break
        discarded+=k-p;p=k
        if p+12>len(data):break
        kind,size=struct.unpack_from('<II',data,p+4)
        if not 24<=size<=65536 or (kind in SIZES and SIZES[kind]!=size):
            p+=1;discarded+=1;continue
        if p+size>len(data):break
        frame=data[p:p+size]
        reason=None
        if frame[-2:]!=b'\x00\xff':tail+=1;reason='tail'
        elif zlib.crc32(frame[12:-12])!=struct.unpack_from('<I',frame,size-12)[0]:crc+=1;reason='crc'
        if reason:
            bad.append((p,kind,size,reason));p+=1;discarded+=1;continue
        seq=struct.unpack_from('<I',frame,12)[0] if kind in (102,104) else None
        if kind in (102,104) and (struct.unpack_from('<I',frame,24)[0]>=1000000000 or
                (kind==102 and struct.unpack_from('<I',frame,128)[0]>300)):
            decode_errors+=1;seq=None
        valid.append((p,kind,seq));p+=size
    histogram=collections.Counter();examples=[];index=0
    for pos,kind,size,reason in bad:
        while index<len(valid) and valid[index][0]<=pos:index+=1
        offset=valid[index][0]-pos if index<len(valid) else None
        difference=size-offset if offset is not None else None
        if difference is not None:histogram[str(difference)]+=1
        if len(examples)<32:examples.append(dict(offset=pos,type=kind,declared_length=size,
            next_valid_header_offset=offset,difference=difference,reason=reason))
    return dict(bytes_received=len(data),valid_frames=len(valid),crc_errors=crc,tail_errors=tail,
        framing_gaps=len(bad),discarded_bytes=discarded,trailing_bytes=len(data)-p,
        decode_errors=decode_errors,
        cloud_frames=sum(k==102 and v is not None for _,k,v in valid),imu_frames=sum(k==104 and v is not None for _,k,v in valid),
        cloud_sequence=sequence(v for _,k,v in valid if k==102 and v is not None),
        imu_sequence=sequence(v for _,k,v in valid if k==104 and v is not None),
        gap_size_histogram=dict(histogram),bad_candidate_examples=examples,
        bad_candidate_count=len(bad))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('input');p.add_argument('--output');a=p.parse_args()
    with pathlib.Path(a.input).open('rb') as f:data=f.read(LIMIT+1)
    result=analyze(data);text=json.dumps(result,indent=2)
    if a.output:
        with pathlib.Path(a.output).open('x',encoding='utf-8') as f:f.write(text)
    else:print(text)

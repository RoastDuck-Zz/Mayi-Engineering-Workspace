"""Analyze real wire-analyzer CSV; do not equate counter gaps with packet loss."""
import collections,csv,json,sys
rows=list(csv.DictReader(open(sys.argv[1],newline='')))
groups=collections.defaultdict(list)
for r in rows:
    if r['sequence']:
        groups[r['type']].append(int(r['sequence']))
result={}
for typ,seq in groups.items():
    pairs=list(zip(seq,seq[1:]))
    exact=sum(a==1023 and b==0 for a,b in pairs)
    modulus=1024 if max(seq)==1023 and exact else None
    abnormal=[(a,b) for a,b in pairs if b!=a+1 and not (modulus and a==1023 and b==0)]
    result[typ]=dict(field='little-endian uint32',documented_semantics='packet sequence consecutively increasing',
        observed_modulus=modulus,confirmed_packet_loss='UNKNOWN',unknown_sequence_discontinuity=len(abnormal),
        sequence_reset='UNKNOWN',sequence_wrap=exact if modulus else 'UNKNOWN',
        observed_min=min(seq),observed_max=max(seq),abnormal_examples=abnormal[:20],
        note='Exact 1023->0 observed; discontinuities across nonadjacent counter values remain UNKNOWN, not network loss.')
with open(sys.argv[2],'w') as s:json.dump(result,s,indent=2)
print(json.dumps(result,indent=2))

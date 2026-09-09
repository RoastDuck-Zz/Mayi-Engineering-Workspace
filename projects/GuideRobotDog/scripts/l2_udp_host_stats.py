"""Read-only Linux UDP and NIC counters with explicit unsupported fields."""
import argparse
import json
import pathlib

UDP_FIELDS=('InDatagrams','NoPorts','InErrors','OutDatagrams','RcvbufErrors','IgnoredMulti')

def rmem_max():
    try:return int(pathlib.Path('/proc/sys/net/core/rmem_max').read_text().strip())
    except OSError:return None

def proc_udp():
    path=pathlib.Path('/proc/net/snmp')
    try: lines=path.read_text().splitlines()
    except OSError:return {'status':'UNSUPPORTED','counters':None}
    for i,line in enumerate(lines[:-1]):
        if line.startswith('Udp:'):
            names=line.split()[1:];values=lines[i+1].split()[1:]
            return {'status':'SUPPORTED','counters':{k:int(v) for k,v in zip(names,values)}}
    return {'status':'UNSUPPORTED','counters':None}

def nic(interface):
    base=pathlib.Path('/sys/class/net')/interface/'statistics'
    fields=('rx_packets','rx_bytes','rx_errors','rx_dropped','rx_missed_errors')
    result={}
    for field in fields:
        try: result[field]=int((base/field).read_text().strip())
        except OSError: result[field]=None
    return {'status':'SUPPORTED' if any(v is not None for v in result.values()) else 'UNSUPPORTED','counters':result}

def snapshot(interface):return {'udp':proc_udp(),'nic':nic(interface),'net_core_rmem_max':rmem_max()}

def delta(a,b):
    out={}
    for group in ('udp','nic'):
        if a[group]['status']!='SUPPORTED' or b[group]['status']!='SUPPORTED':out[group]=None;continue
        out[group]={k:(b[group]['counters'][k]-v if b[group]['counters'][k] is not None and v is not None and b[group]['counters'][k]>=v else None) for k,v in a[group]['counters'].items()}
    return out

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--interface',default='eth0');a=p.parse_args();print(json.dumps(snapshot(a.interface),indent=2))

"""Linux TIOCGICOUNT query only: O_RDONLY, no termios or modem changes."""
import argparse
import errno
import json
import os
import struct

FIELDS=('cts','dsr','rng','dcd','rx','tx','frame','overrun','parity','break','buf_overrun')
TIOCGICOUNT=0x545D # Linux asm-generic/ioctls.h; linux/serial.h 20 native int fields


def read_counters(fd,ioctl=None):
    if ioctl is None:
        import fcntl
        ioctl=fcntl.ioctl
    buffer=bytearray(80)
    try:
        ioctl(fd,TIOCGICOUNT,buffer,True)
        values=struct.unpack('=20i',buffer)
        return {'status':'SUPPORTED','counters':dict(zip(FIELDS,values))}
    except OSError as e:
        return {'status':'UNSUPPORTED' if e.errno in (errno.ENOTTY,errno.EINVAL,errno.EOPNOTSUPP) else 'ERROR',
                'errno':e.errno,'counters':None}


def snapshot(device):
    try:
        fd=os.open(device,os.O_RDONLY|os.O_NOCTTY|os.O_NONBLOCK)
        try: return read_counters(fd)
        finally: os.close(fd)
    except OSError as e: return {'status':'ERROR','errno':e.errno,'counters':None}


def delta(before,after):
    if before['status']!='SUPPORTED' or after['status']!='SUPPORTED': return None
    # Counter reset/wrap is not a negative error delta or a fabricated zero.
    return {k:(after['counters'][k]-v if after['counters'][k]>=v else None) for k,v in before['counters'].items()}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--device',default='/dev/unitree_l2');a=p.parse_args()
    print(json.dumps(snapshot(a.device),indent=2))

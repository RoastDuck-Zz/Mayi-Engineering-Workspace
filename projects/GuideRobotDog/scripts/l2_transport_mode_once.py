"""Explicit, separate one-shot mode activation. Never imported by the monitor.

Unitree v2.0.10 BSD protocol plus pinned setter binary evidence:
GET config: type 100, cmd 6/value 0; mode reply type 107.
SET mode: pinned setLidarWorkMode encodes legacy type 2002, uint32 mode.
RESET: type 100, cmd 1/value 1. No other outgoing packets are supported.
See docs/PHASE_B2_REPORT.md. No SDK library is loaded.
"""
import argparse
import json
import os
import pathlib
import select
import socket
import struct
import time
import zlib

MAGIC=bytes.fromhex('55aa050a')


def _packet(kind,payload):
    return MAGIC+struct.pack('<II',kind,len(payload)+24)+payload+struct.pack('<II',zlib.crc32(payload),0)+bytes.fromhex('000000ff')


QUERY=_packet(100,struct.pack('<II',6,0))
SET8=_packet(2002,struct.pack('<I',8))
SET0=_packet(2002,struct.pack('<I',0))
RESET=_packet(100,struct.pack('<II',1,1))


def mode_from_frame(b):
    if len(b)!=28 or b[:4]!=MAGIC or struct.unpack_from('<II',b,4)!=(107,28): return None
    if b[-2:]!=b'\x00\xff' or zlib.crc32(b[12:-12])!=struct.unpack_from('<I',b,16)[0]: return None
    return struct.unpack_from('<I',b,12)[0]


def execute(transport,activate=False,reset_after_set=False,result=None,target_mode=8):
    if target_mode not in (0,8): raise ValueError('only mode 0 or 8 supported')
    command=SET0 if target_mode==0 else SET8
    if result is None: result={}
    result.update(before=None,after=None,set_sent=False,reset_sent=False,success=False)
    transport.send(QUERY)
    current=transport.receive_mode();result['before']=current
    print('CURRENT MODE:',current if current is not None else 'UNKNOWN',flush=True)
    print('TARGET MODE:',target_mode,flush=True)
    if current is None: return result
    if not activate or current==target_mode:
        result.update(after=current,success=True);return result
    # Activation is explicit and target is restricted to Ethernet0 / Serial8.
    # No arbitrary mode or factory configuration is available.
    print('COMMAND TO BE SENT: SET WORK MODE =',target_mode,'hex='+command.hex(),flush=True)
    transport.send(command);result['set_sent']=True
    time.sleep(.2)
    transport.send(QUERY)
    after=transport.receive_mode();result['after']=after
    if after!=target_mode:
        print('STOP: set acceptance unverified; no retry or reset',flush=True)
        return result
    if reset_after_set:
        print('COMMAND TO BE SENT: L2 RESET; hex='+RESET.hex(),flush=True)
        transport.send(RESET);result['reset_sent']=True
    result['success']=True
    print('Verify mode and streaming independently on the target interface.',flush=True)
    return result


class Connection:
    def __init__(self,args):
        self.sock=None;self.fd=None;self.buffer=bytearray();self.sent=[]
        if args.device:
            import termios
            if not hasattr(termios,'B4000000'): raise RuntimeError('B4000000 unsupported')
            self.fd=os.open(args.device,os.O_RDWR|os.O_NOCTTY|os.O_NONBLOCK)
            try:
                a=termios.tcgetattr(self.fd)
                a[0]=0;a[1]=0;a[3]=0
                a[2] &= ~(termios.CSIZE|termios.PARENB|termios.CSTOPB|termios.CRTSCTS|termios.HUPCL)
                a[2] |= termios.CS8|termios.CLOCAL|termios.CREAD
                a[4]=a[5]=termios.B4000000;a[6][termios.VMIN]=0;a[6][termios.VTIME]=0
                termios.tcsetattr(self.fd,termios.TCSANOW,a)
            except BaseException:
                os.close(self.fd);self.fd=None;raise
        else:
            self.sock=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
            try:
                self.sock.bind((args.host,6201));self.sock.setblocking(False)
                self.peer=(args.lidar,6101)
            except BaseException:
                self.sock.close();raise

    def send(self,b):
        if b not in (QUERY,SET8,SET0,RESET): raise ValueError('command not allowed')
        if b in (SET8,SET0,RESET) and b in self.sent: raise RuntimeError('write may only be sent once')
        # Record attempt before syscall; partial/uncertain sends are never retried.
        self.sent.append(b)
        n=self.sock.sendto(b,self.peer) if self.sock else os.write(self.fd,b)
        if n!=len(b): raise RuntimeError('partial command send; stop and inspect')

    def receive_mode(self):
        deadline=time.monotonic()+3
        self.buffer.clear()
        while time.monotonic()<deadline:
            handle=self.sock if self.sock else self.fd
            if not select.select([handle],[],[],.1)[0]: continue
            if self.sock:
                b,peer=self.sock.recvfrom(65535)
                if peer!=self.peer: continue
            else:
                b=os.read(self.fd,8192)
                if not b: continue
            self.buffer.extend(b)
            while len(self.buffer)>=12:
                index=self.buffer.find(MAGIC)
                if index<0: self.buffer=self.buffer[-3:];break
                if index: del self.buffer[:index]
                if len(self.buffer)<12: break
                size=struct.unpack_from('<I',self.buffer,8)[0]
                if size<24 or size>65536: del self.buffer[0];continue
                if len(self.buffer)<size: break
                frame=bytes(self.buffer[:size]);del self.buffer[:size]
                mode=mode_from_frame(frame)
                if mode is not None: return mode
        return None

    def close(self):
        if self.sock: self.sock.close()
        if self.fd is not None: os.close(self.fd);self.fd=None


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--device');p.add_argument('--host');p.add_argument('--lidar')
    modes=p.add_mutually_exclusive_group()
    modes.add_argument('--activate-mode-8',action='store_true')
    modes.add_argument('--activate-mode-0',action='store_true')
    p.add_argument('--reset-after-verified-set',action='store_true',
                   help='optional L2 reset only after this invocation sets and reads back the target mode')
    p.add_argument('--output',required=True)
    a=p.parse_args()
    if a.reset_after_verified_set and not (a.activate_mode_8 or a.activate_mode_0):
        p.error('--reset-after-verified-set requires an explicit activation flag')
    if bool(a.device)==bool(a.host or a.lidar) or (not a.device and not(a.host and a.lidar)):
        p.error('choose --device OR explicit --host and --lidar')
    if not a.device:
        try: socket.inet_pton(socket.AF_INET,a.host);socket.inet_pton(socket.AF_INET,a.lidar)
        except OSError: p.error('explicit IPv4 addresses required')
    target=pathlib.Path(a.output);target.parent.mkdir(parents=True,exist_ok=True)
    # Refuse overwriting evidence before opening a device or sending anything.
    with target.open('x',encoding='utf-8') as out:
        connection=None;result=dict(success=False)
        try:
            connection=Connection(a)
            execute(connection,a.activate_mode_8 or a.activate_mode_0,a.reset_after_verified_set,result,0 if a.activate_mode_0 else 8)
        except Exception as e:
            result['error']=str(e);print('STOP:',e,flush=True)
        finally:
            if connection:
                result['command_attempts_hex']=[b.hex() for b in connection.sent]
                connection.close()
            json.dump(result,out,indent=2);out.flush()
    return 0 if result['success'] else 1


if __name__=='__main__': raise SystemExit(main())

"""Synthetic Unitree v2.0.10 wire fixtures; struct offsets, independent zlib CRC.
No device capture or identifiers. Executed by test runner into a temporary folder.
"""
import pathlib
import struct
import sys
import zlib


def packet(kind, payload):
    return (bytes.fromhex('55aa050a') + struct.pack('<II', kind, len(payload)+24)
            + payload + struct.pack('<II', zlib.crc32(payload), 0)
            + bytes.fromhex('000000ff'))


def imu(seq=7, sec=10, ns=250000000):
    return packet(104, struct.pack('<IIII10f', seq, 56, sec, ns,
                                  1, 0, 0, 0, 1, 2, 3, 4, 5, 6))


def cloud():
    p = bytearray(1020)
    struct.pack_into('<IIII', p, 0, 9, 1020, 10, 500000000)
    # a,b,theta bias,alpha bias,beta,xi,range bias,range scale
    struct.pack_into('<8f', p, 52, .1, .2, 0, 0, 0, 0, 0, .001)
    # theta start/step, scan period, range min/max, alpha start/step, point dt
    struct.pack_into('<8fI', p, 84, 0, 0, .01, 0, 100, 0, 0, .0001, 2)
    struct.pack_into('<2H', p, 120, 1000, 2000)
    p[720:722] = bytes([42, 99])
    return packet(102, p)


if __name__ == '__main__':
    dest = pathlib.Path(sys.argv[1])
    dest.mkdir(parents=True, exist_ok=True)
    (dest/'imu.bin').write_bytes(imu())
    (dest/'cloud.bin').write_bytes(cloud())
    (dest/'unknown.bin').write_bytes(packet(9876, b'abcd'))

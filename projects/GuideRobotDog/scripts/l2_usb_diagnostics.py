"""Read-only sysfs USB descriptors. Private identity/path redacted by default."""
import argparse
import json
import pathlib
import platform


def read(path):
    try:return path.read_text().strip()
    except OSError:return None


def describe(interface,private=False):
    interface=pathlib.Path(interface).resolve()
    usb=next((p for p in [interface,*interface.parents] if (p/'idVendor').is_file()),None)
    if usb is None:return {'status':'UNAVAILABLE','device_path':'[REDACTED]' if not private else str(interface)}
    drivers=sorted({p.resolve().name for p in usb.glob('*/driver')})
    endpoints=[]
    for ep in sorted(usb.glob('*/ep_*')):
        raw=read(ep/'wMaxPacketSize')
        endpoints.append({'address':read(ep/'bEndpointAddress'),'type':read(ep/'type'),
            'direction':read(ep/'direction'),'wMaxPacketSize_hex':raw,
            'max_packet_bytes':(int(raw,16)&0x7ff) if raw else None})
    result={'status':'AVAILABLE','usb_driver':drivers,'tty_driver':(interface/'driver').resolve().name if (interface/'driver').exists() else None,
            'speed_mbps':read(usb/'speed'),'device_class':read(usb/'bDeviceClass'),
            'vendor_id':read(usb/'idVendor'),'product_id':read(usb/'idProduct'),
            'endpoints':endpoints,'power_control':read(usb/'power/control'),
            'autosuspend_delay_ms':read(usb/'power/autosuspend_delay_ms'),
            'runtime_status':read(usb/'power/runtime_status'),'device_path':'[REDACTED]',
            'usb_serial':'[REDACTED]','usb_bus_port':'[REDACTED]'}
    if private:result.update(device_path=str(interface),usb_serial=read(usb/'serial'),usb_bus_port=usb.name)
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--device',default='/dev/unitree_l2');p.add_argument('--private',action='store_true');a=p.parse_args()
    tty=pathlib.Path(a.device).resolve().name
    result=describe(pathlib.Path('/sys/class/tty')/tty/'device',a.private)
    result.update(kernel=platform.release(),machine=platform.machine())
    print(json.dumps(result,indent=2))

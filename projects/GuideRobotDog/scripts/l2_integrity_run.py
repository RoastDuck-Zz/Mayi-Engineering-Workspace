"""Private host evidence around a bounded read-only monitor/capture run.

No priority, kernel, USB, or device configuration changes. Run on Linux.
"""
import argparse
import json
import os
import pathlib
import subprocess
import time

from l2_tty_stats import snapshot, delta


def kernel(path):
    result=subprocess.run(['dmesg'],capture_output=True,text=True)
    path.write_text(result.stdout if result.returncode==0 else 'UNAVAILABLE\n'+result.stderr)
    return result.returncode


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--device',default='/dev/unitree_l2')
    parser.add_argument('--executable',required=True)
    parser.add_argument('--prefix',required=True)
    parser.add_argument('--seconds',type=int,choices=(5,10,60),default=10)
    parser.add_argument('--read-size',type=int,choices=(1024,4096,8192,16384,32768),default=8192)
    parser.add_argument('--capture',action='store_true')
    args=parser.parse_args()
    if args.capture and args.seconds>10:parser.error('capture maximum is 10 seconds')
    os.umask(0o077)
    prefix=pathlib.Path(args.prefix)
    # A unique run directory avoids replacing an earlier evidence set.
    prefix.mkdir(mode=0o700)
    before=snapshot(args.device)
    kb=kernel(prefix/'kernel-before.txt')
    command=[args.executable,'--device',args.device,'--seconds',str(args.seconds),
             '--output',str(prefix/('raw.bin' if args.capture else 'monitor'))]
    if not args.capture:command+=['--read-size',str(args.read_size)]
    samples=[];start=time.monotonic()
    with (prefix/'stdout.txt').open('x') as stdout,(prefix/'stderr.txt').open('x') as stderr:
        process=subprocess.Popen(command,stdout=stdout,stderr=stderr)
        try:
            while process.poll() is None:
                status=pathlib.Path(f'/proc/{process.pid}/status')
                try:
                    selected=[s for s in status.read_text().splitlines() if s.startswith(
                        ('State:','voluntary_ctxt_switches:','nonvoluntary_ctxt_switches:','Cpus_allowed_list:'))]
                    cpu=pathlib.Path('/proc/stat').read_text().splitlines()[0]
                    samples.append(dict(elapsed=time.monotonic()-start,load=os.getloadavg(),
                                        process_status=selected,system_cpu_ticks=cpu))
                except FileNotFoundError:pass
                if time.monotonic()-start>args.seconds+10:
                    process.terminate()
                    try:process.wait(timeout=3)
                    except subprocess.TimeoutExpired:process.kill();process.wait()
                    break
                time.sleep(.25)
        finally:
            if process.poll() is None:
                process.terminate()
                try:process.wait(timeout=3)
                except subprocess.TimeoutExpired:process.kill();process.wait()
    after=snapshot(args.device)
    ka=kernel(prefix/'kernel-after.txt')
    report=dict(exit_code=process.returncode,elapsed=time.monotonic()-start,
                tty_errors_before=before,tty_errors_after=after,tty_errors_delta=delta(before,after),
                kernel_before_exit=kb,kernel_after_exit=ka,scheduling_samples=samples)
    (prefix/'host.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(dict(run=prefix.name,exit_code=process.returncode,tty_delta=report['tty_errors_delta'])),flush=True)
    return process.returncode


if __name__=='__main__':raise SystemExit(main())

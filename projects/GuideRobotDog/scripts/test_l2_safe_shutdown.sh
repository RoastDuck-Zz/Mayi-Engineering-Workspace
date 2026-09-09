#!/usr/bin/env bash
# Actual hardware tests; do not run concurrently with another UDP 6201 consumer.
set -u
root=$(cd -- "$(dirname -- "$0")/.." && pwd)
out="$root/reports/phase2"
mkdir -p "$out"
for signal in INT TERM; do
  prefix="$out/safe-$signal"
  "$root/l2_monitor_safe" 192.168.1.62 192.168.1.2 120 "$prefix" > "$prefix.log" 2>&1 &
  task_pid=$!
  sleep 3
  kill -s "$signal" "$task_pid" || exit 1
  wait "$task_pid"; rc=$?
  echo "$rc" > "$prefix-exit.txt"
  python3 - "$prefix" "$signal" "$rc" <<'PY'
import json,socket,sys
p,signal,rc=sys.argv[1:]
summary=json.load(open(p+'-summary.json')); parent=json.load(open(p+'-supervisor.json'))
assert int(rc)==10, (rc,summary,parent) # Short test must not claim 60-second runtime PASS.
assert parent['wrapper_cleanup']=='PASS' and not parent['forced_kill']
assert summary['runtime_path']=='INCOMPLETE' and summary['clouds']>0
assert summary['stopped_by_signal']=={'INT':2,'TERM':15}[signal]
with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as s:s.bind(('192.168.1.2',6201))
print('PASS',signal,'reports saved, runtime explicitly INCOMPLETE, child reaped, UDP port reusable')
PY
  [[ $? == 0 ]] || exit 1
done

# Deliberately abort only the test's SDK child to prove the supervisor preserves failure.
prefix="$out/safe-runtime-abort"
"$root/l2_monitor_safe" 192.168.1.62 192.168.1.2 120 "$prefix" > "$prefix.log" 2>&1 &
task_pid=$!
sleep 2
python3 - "$task_pid" <<'PY'
import os,pathlib,signal,sys
parent=int(sys.argv[1]); children=pathlib.Path(f'/proc/{parent}/task/{parent}/children').read_text().split()
assert len(children)==1, children
os.kill(int(children[0]),signal.SIGKILL)
PY
wait "$task_pid"; rc=$?
echo "$rc" > "$prefix-exit.txt"
python3 - "$prefix" "$rc" <<'PY'
import json,sys
p,rc=sys.argv[1:]; s=json.load(open(p+'-supervisor.json'))
assert int(rc)==137 and s['runtime_path']=='FAIL' and s['wrapper_cleanup']=='FAIL', s
print('PASS failure propagation: intentionally aborted test child remains runtime FAIL, exit 137')
PY

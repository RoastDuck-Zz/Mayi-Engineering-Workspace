#!/usr/bin/env bash
set -eu
root=$(cd -- "$(dirname -- "$0")/.." && pwd)
seconds=${1:-10}
out=${2:-"$root/reports/official-sdk-${seconds}s"}
mkdir -p "$(dirname -- "$out")"
set +e
timeout "$((seconds+15))" "$root/build-official/l2_official_sdk_probe" "$seconds" >"$out.json" 2>"$out.stderr"
status=$?
set -e
python3 - "$out.json" "$out.stderr" "$status" <<'PY'
import json, pathlib, sys
out, err = map(pathlib.Path, sys.argv[1:3])
code = int(sys.argv[3])
data = json.loads(out.read_text()) if out.exists() and out.stat().st_size else {}
data['process_exit_code'] = code
data['close_returned'] = 'CHECKPOINT after closeUDP' in err.read_text(errors='replace') if err.exists() else False
data['sdk_cleanup'] = 'PASS' if data['close_returned'] else 'FAIL_KNOWN_CLOSEUDP'
out.write_text(json.dumps(data, indent=2) + '\n')
PY
exit 0

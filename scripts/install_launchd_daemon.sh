#!/bin/zsh
set -euo pipefail

ENV_FILE="/Users/ericfeunekes/Library/Application Support/wxbench/wxbench.env"
RUN_SCRIPT="/Users/ericfeunekes/coding/weather-service-testing/scripts/run_hourly_daemon.sh"
LAUNCHD_LABEL="com.wxbench.hourly"
DATA_ROOT="/Users/ericfeunekes/Library/Application Support/wxbench"

if [ ! -f "$ENV_FILE" ]; then
  echo "Missing env file: $ENV_FILE" >&2
  exit 2
fi

while IFS= read -r line; do
  [ -z "$line" ] && continue
  case "$line" in
    \#*) continue ;;
  esac
  if [[ "$line" == *"="* ]]; then
    export "$line"
  fi
done < "$ENV_FILE"

missing=0
for key in WX_LAT WX_LON WX_TZ; do
  if [ -z "${(P)key:-}" ]; then
    echo "Missing required env var: $key" >&2
    missing=1
  fi
done
if [ "$missing" -ne 0 ]; then
  exit 2
fi

if [ ! -x "$RUN_SCRIPT" ]; then
  echo "Missing run script: $RUN_SCRIPT" >&2
  exit 2
fi

tee /Library/LaunchDaemons/com.wxbench.hourly.plist > /dev/null <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.wxbench.hourly</string>
  <key>UserName</key>
  <string>ericfeunekes</string>
  <key>ProgramArguments</key>
  <array>
  <string>/Users/ericfeunekes/coding/weather-service-testing/scripts/run_hourly_daemon.sh</string>
  </array>
  <key>RunAtLoad</key>
  <true/>
  <key>StartInterval</key>
  <integer>900</integer>
  <key>WorkingDirectory</key>
  <string>/Users/ericfeunekes/coding/weather-service-testing</string>
  <key>StandardOutPath</key>
  <string>/Users/ericfeunekes/Library/Application Support/wxbench/launchd.out.log</string>
  <key>StandardErrorPath</key>
  <string>/Users/ericfeunekes/Library/Application Support/wxbench/launchd.err.log</string>
</dict>
</plist>
PLIST

chown root:wheel /Library/LaunchDaemons/com.wxbench.hourly.plist
chmod 644 /Library/LaunchDaemons/com.wxbench.hourly.plist

launchctl bootout system/$LAUNCHD_LABEL >/dev/null 2>&1 || true
launchctl bootstrap system /Library/LaunchDaemons/com.wxbench.hourly.plist
launchctl enable system/com.wxbench.hourly
launchctl kickstart -k system/$LAUNCHD_LABEL

echo "---- launchd status ----"
launchctl print system/$LAUNCHD_LABEL || true

echo "---- launchd logs (last 50) ----"
if [ -f "$DATA_ROOT/launchd.out.log" ]; then
  tail -n 50 "$DATA_ROOT/launchd.out.log"
else
  echo "missing: $DATA_ROOT/launchd.out.log"
fi
if [ -f "$DATA_ROOT/launchd.err.log" ]; then
  tail -n 50 "$DATA_ROOT/launchd.err.log"
else
  echo "missing: $DATA_ROOT/launchd.err.log"
fi

echo "---- latest run ----"
if [ -d "$DATA_ROOT/runs" ]; then
  latest_run=$(ls -1t "$DATA_ROOT/runs" | head -n 1 || true)
  if [ -n "$latest_run" ]; then
    echo "run_id: $latest_run"
    if [ -f "$DATA_ROOT/runs/$latest_run/manifest.json" ]; then
      cat "$DATA_ROOT/runs/$latest_run/manifest.json"
    else
      echo "missing: $DATA_ROOT/runs/$latest_run/manifest.json"
    fi
    echo "----"
    if [ -f "$DATA_ROOT/runs/$latest_run/logs.jsonl" ]; then
      tail -n 30 "$DATA_ROOT/runs/$latest_run/logs.jsonl"
    else
      echo "missing: $DATA_ROOT/runs/$latest_run/logs.jsonl"
    fi
  else
    echo "no run directories found"
  fi
else
  echo "missing: $DATA_ROOT/runs"
fi

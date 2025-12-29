#!/bin/zsh
set -euo pipefail

LAUNCHD_LABEL="com.wxbench.hourly"
DATA_ROOT="$HOME/Library/Application Support/wxbench"

sudo launchctl print system/$LAUNCHD_LABEL || true

echo "---- launchd logs ----"
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
    latest_manifest="$DATA_ROOT/runs/$latest_run/manifest.json"
    hour_bucket=""
    if [ -f "$latest_manifest" ]; then
      hour_bucket=$(grep -E '"hour_bucket"' "$latest_manifest" | head -n 1 | awk -F\" '{print $4}')
    fi
    success_run=""
    if [ -n "$hour_bucket" ]; then
      for run_dir in $(ls -1t "$DATA_ROOT/runs"); do
        manifest="$DATA_ROOT/runs/$run_dir/manifest.json"
        if [ -f "$manifest" ]; then
          hb=$(grep -E '"hour_bucket"' "$manifest" | head -n 1 | awk -F\" '{print $4}')
          run_status=$(grep -E '"status"' "$manifest" | head -n 1 | awk -F\" '{print $4}')
          if [ "$hb" = "$hour_bucket" ] && [ "$run_status" = "success" ]; then
            success_run="$run_dir"
            break
          fi
        fi
      done
    fi

    if [ -n "$success_run" ]; then
      target_run="$success_run"
      echo "latest successful run (hour bucket $hour_bucket): $target_run"
    else
      target_run="$latest_run"
      echo "latest run: $target_run"
    fi

    if [ -f "$DATA_ROOT/runs/$target_run/manifest.json" ]; then
      cat "$DATA_ROOT/runs/$target_run/manifest.json"
    else
      echo "missing: $DATA_ROOT/runs/$target_run/manifest.json"
    fi
    echo "----"
    if [ -f "$DATA_ROOT/runs/$target_run/logs.jsonl" ]; then
      tail -n 30 "$DATA_ROOT/runs/$target_run/logs.jsonl"
    else
      echo "missing: $DATA_ROOT/runs/$target_run/logs.jsonl"
    fi
  else
    echo "no run directories found"
  fi
else
  echo "missing: $DATA_ROOT/runs"
fi

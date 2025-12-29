#!/bin/zsh
set -euo pipefail

if launchctl print system/com.wxbench.hourly >/dev/null 2>&1; then
  launchctl bootout system/com.wxbench.hourly || true
fi

rm -f /Library/LaunchDaemons/com.wxbench.hourly.plist

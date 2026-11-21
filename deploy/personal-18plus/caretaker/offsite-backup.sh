#!/bin/sh
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copies rexctl's backups to off-site storage with rclone, so a dead server
# doesn't take your community with it. Does nothing until OFFSITE_REMOTE is set.
set -eu

: "${OFFSITE_REMOTE:=}"
: "${OFFSITE_KEEP_DAYS:=30}"
: "${FLUXER_DIR:=/opt/fluxer}"
: "${REXCTL:=/usr/local/bin/rexctl}"

if [ -z "$OFFSITE_REMOTE" ]; then
	echo "OFFSITE_REMOTE is empty, skipping off-site copy."
	exit 0
fi

backup_dir=$("$REXCTL" backup location --dir "$FLUXER_DIR" --json 2>/dev/null \
	| python3 -c 'import json,sys; d=json.load(sys.stdin); print(d.get("location") or d.get("folder") or d.get("path") or "")' \
	|| true)
[ -n "$backup_dir" ] || backup_dir="$FLUXER_DIR/backups"

if rclone copy "$backup_dir" "$OFFSITE_REMOTE" --include '*.tar.zst' --transfers 2; then
	rclone delete "$OFFSITE_REMOTE" --min-age "${OFFSITE_KEEP_DAYS}d" --include '*.tar.zst' || true
	echo "Off-site copy finished."
else
	python3 /opt/fluxer-caretaker/caretaker.py alert "Backup problem" "Copying backups to $OFFSITE_REMOTE failed." --urgent || true
	echo "Off-site copy FAILED" >&2
	exit 1
fi

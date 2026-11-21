#!/bin/sh
# SPDX-License-Identifier: AGPL-3.0-or-later
# Step 2: install the maintenance bots and switch on the adults-only settings.
# Run as root after /etc/fluxer-caretaker.env is filled in:
#
#   sudo sh install-bots.sh
set -eu

here=$(cd "$(dirname "$0")" && pwd)
env_file=/etc/fluxer-caretaker.env

if [ "$(id -u)" -ne 0 ]; then
	echo "Please run this as root (sudo sh install-bots.sh)." >&2
	exit 1
fi
if [ ! -f "$env_file" ]; then
	cp "$here/caretaker/caretaker.env.example" "$env_file"
	chmod 600 "$env_file"
	echo "Created $env_file. Fill it in (nano $env_file), then run this again."
	exit 1
fi
chmod 600 "$env_file"
# shellcheck disable=SC1090
. "$env_file"

echo "==> Installing the caretaker bots"
install -d -m 0755 /opt/fluxer-caretaker
install -m 0755 "$here/caretaker/caretaker.py" /opt/fluxer-caretaker/caretaker.py
install -m 0755 "$here/caretaker/offsite-backup.sh" /opt/fluxer-caretaker/offsite-backup.sh
if [ -f "$here/branding/porchlite-theme.css" ]; then
	install -m 0644 "$here/branding/porchlite-theme.css" /opt/fluxer-caretaker/theme.css
fi
if [ -d "$here/branding/badges" ]; then
	install -d -m 0755 /opt/fluxer-caretaker/badges
	install -m 0644 "$here"/branding/badges/*.png /opt/fluxer-caretaker/badges/
fi
if [ -d "$here/branding/levels" ]; then
	install -d -m 0755 /opt/fluxer-caretaker/levels
	install -m 0644 "$here"/branding/levels/*.png /opt/fluxer-caretaker/levels/
fi
install -m 0644 "$here"/systemd/*.service "$here"/systemd/*.timer /etc/systemd/system/
systemctl daemon-reload

echo "==> Checking notifications"
python3 /opt/fluxer-caretaker/caretaker.py test-notify

echo "==> Turning on the adults-only settings"
python3 /opt/fluxer-caretaker/caretaker.py apply-settings

if [ -f "$here/branding/porchlite-logo-512.png" ]; then
	echo "==> Applying the logo, icon and colour"
	rexctl branding set \
		--name "${INSTANCE_NAME:-Porchlite}" \
		--colour "${BRAND_COLOR:-#D9A95B}" \
		--logo "$here/branding/porchlite-logo-512.png" \
		--icon "$here/branding/porchlite-favicon-512.png" || echo "Branding failed; you can upload it in /admin instead."
fi

echo "==> Starting the age-gate, reports and health bots"
systemctl enable --now fluxer-caretaker-age-gate.timer fluxer-caretaker-reports.timer fluxer-caretaker-health.timer

if [ -n "${BADGE_GUILD_ID:-}" ]; then
	echo "==> Uploading the badges and starting the badge bot"
	python3 /opt/fluxer-caretaker/caretaker.py badges-setup || echo "Badge upload failed; check the API key permissions."
	systemctl enable --now fluxer-caretaker-badges.timer
else
	echo "==> Badge bot skipped (BADGE_GUILD_ID is empty)"
fi

if [ -n "${GUILD_LEVELS:-}" ]; then
	echo "==> Uploading the level badges and starting server levels ($GUILD_LEVELS members)"
	python3 /opt/fluxer-caretaker/caretaker.py levels-setup || echo "Level badge upload failed; check the API key permissions."
	systemctl enable --now fluxer-caretaker-levels.timer
else
	echo "==> Server levels skipped (GUILD_LEVELS is empty)"
fi

echo "==> Weekly automatic upgrades (Sunday 04:00), each with a backup first,"
echo "    plus a full backup with uploads on the 1st of every month"
if [ -n "${NOTIFY_URL:-}" ]; then
	rexctl auto-upgrade on --day sun --at 04:00 --backup full --full-backup monthly --notify "$NOTIFY_URL"
else
	rexctl auto-upgrade on --day sun --at 04:00 --backup full --full-backup monthly
fi

if [ -n "${OFFSITE_REMOTE:-}" ]; then
	echo "==> Off-site backup copies to $OFFSITE_REMOTE"
	command -v rclone >/dev/null 2>&1 || apt-get install -yq rclone
	systemctl enable --now fluxer-offsite-backup.timer
else
	echo "==> Off-site backups skipped (OFFSITE_REMOTE is empty)"
fi

echo
echo "All set. See what the bots are doing with:"
echo "  systemctl list-timers 'fluxer-*'"
echo "  journalctl -u 'fluxer-caretaker@*' --since today"

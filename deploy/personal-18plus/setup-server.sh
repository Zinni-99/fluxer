#!/bin/sh
# SPDX-License-Identifier: AGPL-3.0-or-later
# Step 1: install Fluxer on a fresh Ubuntu/Debian server, set up for an
# adults-only community. Run as root:
#
#   sudo sh setup-server.sh chat.example.com
#
# Before running it, point the domain's A record at this server's IP address.
set -eu

domain=${1:-}
if [ -z "$domain" ]; then
	printf 'Domain for your server (like chat.example.com): '
	read -r domain
fi
if [ "$(id -u)" -ne 0 ]; then
	echo "Please run this as root (sudo sh setup-server.sh $domain)." >&2
	exit 1
fi

echo "==> Updating the system and turning on automatic security updates"
export DEBIAN_FRONTEND=noninteractive
apt-get update -q
apt-get upgrade -yq
apt-get install -yq unattended-upgrades python3 curl ufw fail2ban
dpkg-reconfigure -f noninteractive unattended-upgrades

echo "==> Firewall: SSH, web, and voice ports only"
ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw allow 443/udp
ufw allow 7881/tcp
ufw allow 7882/udp
ufw --force enable

# Small machines (like a 4 GB Raspberry Pi): add swap and use Fluxer's small
# memory profile so it fits. Bigger machines skip this.
mem_mb=$(awk '/MemTotal/ {print int($2/1024)}' /proc/meminfo)
small_flags=""
if [ "$mem_mb" -lt 6000 ]; then
	echo "==> Only ${mem_mb} MB of memory: adding 4 GB of swap and using the small profile"
	if ! swapon --show | grep -q /swapfile; then
		fallocate -l 4G /swapfile || dd if=/dev/zero of=/swapfile bs=1M count=4096
		chmod 600 /swapfile
		mkswap /swapfile
		swapon /swapfile
		grep -q '^/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
	fi
	sysctl -w vm.swappiness=10 >/dev/null
	echo 'vm.swappiness=10' > /etc/sysctl.d/90-fluxer-swap.conf
	small_flags="--memory-profile small"
fi

echo "==> Installing Fluxer with rexctl (it will ask you a few questions)"
# registration=approval: anyone can ask to join, nobody gets in until approved.
# The age-gate bot (install-bots.sh) turns away anyone who says they are under 18.
curl -fsSL https://fluxer.dev/install.sh | sh -s -- install \
	--domain "$domain" \
	--registration approval \
	--sign-in email \
	--boot-service on \
	$small_flags

if [ -n "$small_flags" ]; then
	# Run background jobs inside the api service: one less service in memory.
	rexctl config set FLUXER_API_EMBEDDED_WORKER true
	rexctl doctor --fix --yes || true
fi

echo "==> Keeping 7 backups on this machine"
rexctl backup keep 7

cat <<NEXT

Fluxer is installed at https://$domain

Next:
  1. Sign in to https://$domain/admin with the admin account you just made.
  2. Open "Admin API Keys" and create a key for the bots (permissions are
     listed in caretaker/caretaker.env.example).
  3. Copy caretaker/caretaker.env.example to /etc/fluxer-caretaker.env,
     fill it in, then run:  sudo sh install-bots.sh
NEXT

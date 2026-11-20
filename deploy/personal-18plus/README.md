# Z's Place: personal adults-only Fluxer server

Everything you need to run your own private, 18+ Fluxer server, plus small bots that look after it. It uses the official installer (`rexctl`) for the hard parts, so you never have to touch Docker files.

Nothing here spends money or deploys anything by itself. You run the two scripts on a server you rent.

## What you'll end up with

- Your own Fluxer at an address like `https://chat.example.com`, usable in a browser and in the Fluxer desktop and phone apps.
- **18+ only:** everyone gives a date of birth at sign-up, nobody gets in until approved, and a bot turns away anyone who says they're under 18.
- **Rules and terms** that people see before they join ([`legal/`](legal/)).
- **Bots** that send alerts to your phone:

| Bot | What it does | How often |
| --- | --- | --- |
| Age gate | Rejects sign-ups under 18, pings you to approve the rest (or approves adults by itself if you choose) | every 5 min |
| Reports | Tells you about every new report, marked urgent if it involves a minor | every 5 min |
| Health | Checks the server is up, responding and not running out of disk | every 10 min |
| Updates | Installs new Fluxer releases, with a backup first and an automatic undo if it fails (built into `rexctl`) | Sundays 04:00 |
| Backups | Backup before every update, full backup with uploads on the 1st of each month, optional copy to cloud storage | weekly / monthly / daily |

The bots never ban anyone for what they post. That stays your call.

## What it costs

| Item | Typical price | Notes |
| --- | --- | --- |
| Server (VPS) | about $15–30 / month | 4 CPU cores, 8 GB memory, 160 GB+ disk. 4 GB works for a handful of friends |
| Domain name | about $10–20 / year | Any registrar. You can also use a subdomain of one you own |
| Off-site backups (optional) | a few dollars / month | e.g. Backblaze B2 or any S3-style storage, via rclone |
| Notifications | free | the ntfy phone app, or a Discord webhook |

### Picking a hosting provider

**Check the acceptable-use policy before you pay.** Many popular providers limit or ban sexually explicit material even when it's legal and private, and they can shut a server down without warning. Look for wording like "adult content", "pornography" or "erotic material" in the provider's acceptable-use or content policy, and pick one that clearly allows legal adult content. Also check:

- The server is in a country whose laws you're comfortable with. Adult-content and age-check laws differ a lot (the UK, parts of the EU and several US states require stronger age checks for sites that publish porn to the public).
- It gives you a public IPv4 address and lets you open ports 80, 443, 7881 and 7882.
- It runs Ubuntu 24.04 or Debian 12/13.

### Running it at home instead (cheapest)

A spare computer with 8 GB of memory, or a Raspberry Pi 5 with 8 GB, runs Fluxer for the price of a domain and some electricity. No hosting company's content rules apply. Install Ubuntu 24.04 or Raspberry Pi OS (64-bit) on it, then follow the steps below with these changes:

- **Reaching it from outside:** in your router, forward TCP ports 80, 443 and 7881 and UDP ports 443 and 7882 to the machine. Give it a fixed local IP in the router's settings so the forwarding keeps working.
- **Home IP addresses change.** Use a domain or DNS service with dynamic DNS (for example Cloudflare DNS with `ddclient`, or Duck DNS), so your domain follows your home IP.
- **Can't forward ports** (some internet providers block it): install with `--behind-proxy` and use Cloudflare Tunnel, as the [Fluxer docs](https://docs.fluxer.com/operator/#without-a-public-ip-address) explain. Text, images and video work, but voice calls need a separate cheap server for relaying them.
- **On a 4 GB Raspberry Pi** (a Pi 4 or Pi 5): `setup-server.sh` notices the small memory and adds 4 GB of swap, uses Fluxer's small memory profile and runs background jobs inside the API to save memory. 4 GB is Fluxer's minimum, so it's fine for a small group (roughly 5–20 people) but can feel slow at busy moments, and video calls with several people at once may struggle. Use a USB SSD rather than the SD card: SD cards are slow for a database and wear out.
- Keep the machine plugged in and on. Off-site backups (`OFFSITE_REMOTE`) matter more at home, in case the disk dies.

## Setting it up (about 30 minutes)

1. **Rent the server** with Ubuntu 24.04. Note its IP address.
2. **Point your domain at it:** at your domain registrar, add an `A` record for `chat` (or whatever you like) with the server's IP.
3. **Log in to the server** (`ssh root@your-server-ip`) and get these files:
   ```sh
   apt-get update && apt-get install -y git
   git clone https://github.com/Zinni-99/fluxer
   cd fluxer/deploy/personal-18plus
   ```
4. **Install Fluxer:**
   ```sh
   sudo sh setup-server.sh chat.example.com
   ```
   It updates the system, sets up the firewall, then runs the Fluxer installer, which asks a few questions (choose to create the admin account in the terminal). For email (needed for password resets and sign-up confirmation) you can use any SMTP service, or skip it and set it up later with `rexctl email set`.
5. **Get a key for the bots:** sign in at `https://chat.example.com/admin`, open **Admin API Keys**, and create a key with only these permissions: `instance:config:view`, `instance:config:update`, `registration:review`, `user:lookup`, `user:view:dob`, `report:view`.
6. **Set up notifications:** install the free **ntfy** app on your phone and subscribe to a long random topic name, like `myserver-k38dj2la9`.
7. **Fill in the bot settings and start them:**
   ```sh
   sudo sh install-bots.sh      # creates /etc/fluxer-caretaker.env the first time
   sudo nano /etc/fluxer-caretaker.env
   sudo sh install-bots.sh      # run again once it's filled in
   ```
   You should get a test notification on your phone. This also turns on the 18+ settings.
8. **Fill in the legal templates** in [`legal/`](legal/) (your domain, contact address, hosting country) and push them to your GitHub fork, or set `LEGAL_BASE_URL` to wherever you publish them, then run `sudo python3 /opt/fluxer-caretaker/caretaker.py apply-settings` again.
9. **Make your community:** in the app, create your community and mark the explicit channels as NSFW (age-restricted) in each channel's settings.

## Inviting people

- People can sign up at your address and wait for approval. You get a ping and approve with one click in `/admin` or with `rexctl registration approve <id>`.
- Or send a personal invite link: `rexctl invites create --uses 1 --expires 7d`.
- For invite-links-only, set `REGISTRATION_MODE=closed` in `/etc/fluxer-caretaker.env` and run `apply-settings` again.

## About age checks

Fluxer asks for a date of birth and blocks accounts that haven't given one (`date_of_birth: require_all`). Out of the box Fluxer only enforces a minimum of 13–16 depending on country, so the age-gate bot adds the 18+ rule by rejecting pending sign-ups under 18.

This is **self-declared** age, which is what most private communities rely on, combined with you approving each member. It is not ID verification. If you ever open the server to the public, check whether your country or state requires a proper age-verification service.

## Day-to-day commands

```sh
rexctl status                       # is everything running?
rexctl doctor                       # find and explain problems
rexctl backup                       # make a backup now
rexctl backup list                  # see backups
rexctl upgrade --check              # is there an update?
rexctl auto-upgrade                 # when the next automatic update runs
rexctl users ban <name> --reason adult-content --delete-messages
systemctl list-timers 'fluxer-*'    # when the bots run next
journalctl -u 'fluxer-caretaker@*' --since today   # what the bots did
```

## Files here

| File | Purpose |
| --- | --- |
| `setup-server.sh` | Step 1: hardens a fresh server and installs Fluxer with sign-up approval |
| `install-bots.sh` | Step 2: installs the bots, schedules updates and backups, applies 18+ settings |
| `caretaker/caretaker.py` | The bots (Python standard library only) |
| `caretaker/caretaker.env.example` | Settings for the bots |
| `caretaker/offsite-backup.sh` | Daily copy of backups to cloud storage with rclone |
| `systemd/` | Timers that run the bots |
| `legal/` | Rules, terms and privacy templates |

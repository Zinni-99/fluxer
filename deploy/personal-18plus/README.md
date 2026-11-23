# Porchlite: personal adults-only Fluxer server

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

## Badges

The kit comes with 14 profile badges (Peach Fuzz, Brat Energy, OG Porchlite and more) in
[`branding/badges/`](branding/badges/). Like staff badges, members can't pick them
themselves; you or the badge bot hand them out.

1. Give the admin API key the badge permissions listed in `caretaker.env.example`.
2. Set `BADGE_GUILD_ID` to your main community's ID, and optionally `BADGE_OG_BEFORE`.
3. Run `sudo sh install-bots.sh` again. It uploads the badges and starts the bot, which checks every 15 minutes.

The rules:

- **Peach Fuzz** for the first `BADGE_PEACH_FUZZ_DAYS` days (14 by default) after someone joins.
- **OG Porchlite** for good, for everyone who joined before `BADGE_OG_BEFORE`.
- **Every other badge** follows a server role with the same name. Make roles such as
  "Brat Energy" or "Hype Fairy" and put them in a role picker, or give them by hand,
  and the badge comes and goes with the role.

You can still give any badge by hand in the admin panel (open the user, Badges tab).
The bot never takes away a badge it didn't give.

## Server levels

Communities level up from how many members they have instead of from boosts. The caretaker checks every 15 minutes and unlocks perks that would normally need boosts:

| Level | Members (default) | Unlocks |
|---|---|---|
| 🕯️ 1 Porch Light | 10 | Better voice (128 kbps), more emoji slots |
| 🏡 2 Cozy Cottage | 25 | 256 kbps voice, more sticker slots |
| 🌙 3 Moonlit Garden | 50 | 384 kbps voice, unlimited emoji and stickers, custom invite link |

Each community also gets a level badge next to its name ([`branding/levels/`](branding/levels/)). On every level-up the owner gets a system DM and you get an alert. A community keeps its best level if people leave, unless you set `GUILD_LEVELS_KEEP=false`. Animated icons and banners are already free for everyone.

To turn it on for an existing install:
1. In `/admin`, **Admin API Keys**, give your key these extra permissions: `guild:update:features`, `guild:update:badges`, `system_dm:send` (plus `guild:lookup`, `badge:list` and `badge:create` if you skipped the badge bot).
2. Add the settings and re-run the installer:
   ```sh
   cd ~/fluxer && git pull
   printf 'GUILD_LEVELS=10,25,50\nGUILD_LEVELS_KEEP=true\n' | sudo tee -a /etc/fluxer-caretaker.env
   cd deploy/personal-18plus && sudo sh install-bots.sh
   ```
3. Check it: `sudo python3 /opt/fluxer-caretaker/caretaker.py levels` should end with "Server levels checked".

Change the numbers any time by editing `GUILD_LEVELS` in `/etc/fluxer-caretaker.env`. Perks the bot didn't give (ones you switched on yourself in `/admin`) are never taken away.

## Hub community

Porchlite can drop every new member into one shared community (the hub), so nobody lands in an empty app. Once someone is approved, the caretaker adds them to the hub within five minutes. Each person is added once: if they leave or you ban them from the hub, they are never pulled back in.

Because the whole instance is 18+ and approval-only, communities made here don't need age gating of their own. Anyone approved can create a community (in `/admin`, **Instance Config**, "Who can create communities" is set to Everyone by default).

To turn it on:
1. In `/admin`, **Admin API Keys**, create a new key with the permissions you already use plus `guild:force_add_member`, `guild:lookup` and `guild:list:members`. Put it in `/etc/fluxer-caretaker.env` as `FLUXER_ADMIN_API_KEY`, then revoke the old key.
2. Add the hub's ID and re-run the installer:
   ```sh
   cd ~/fluxer && git pull
   echo 'HUB_GUILD_ID=your-hub-id' | sudo tee -a /etc/fluxer-caretaker.env
   cd deploy/personal-18plus && sudo sh install-bots.sh
   ```
   The first run only notes who already has an account; from then on, new members are added.
3. To also add everyone who already has an account, run this once:
   ```sh
   sudo python3 /opt/fluxer-caretaker/caretaker.py hub-backfill
   ```
   Run it soon after making the hub. It can't see bans made before the hub was switched on, so someone banned from the hub before then would be added back.

## Terms, privacy and rules website

[`legal/build.py`](legal/build.py) turns `legal/TERMS.md`, `PRIVACY.md` and `RULES.md` into a small Porchlite-styled website (in [`legal/site/`](legal/site/)), with light and dark modes. Cloudflare Pages hosts it for free at `legal.porchlite.xyz` and rebuilds it every time the Markdown changes on GitHub.

These pages are a starting point, not legal advice. Laws about adult content and age checks differ by country and US state, so have them checked before you open Porchlite to the public.

**Set up Cloudflare Pages (once):**
1. In the Cloudflare dashboard, open **Workers & Pages**, then **Create**, choose **Pages**, then **Import an existing Git repository** (connect GitHub if it asks).
2. Pick the `fluxer` repository and fill in:
   - Production branch: `main`
   - Framework preset: `None`
   - Build command: `python3 deploy/personal-18plus/legal/build.py`
   - Build output directory: `deploy/personal-18plus/legal/site`
3. **Save and Deploy**. When it finishes, open the project's **Custom domains** tab, add `legal.porchlite.xyz`, and accept the DNS record Cloudflare offers.
4. Point the sign-up page at it:
   ```sh
   sudo sed -i 's#^LEGAL_BASE_URL=.*#LEGAL_BASE_URL=https://legal.porchlite.xyz#' /etc/fluxer-caretaker.env
   cd ~/fluxer && git pull && sudo install -m 0755 deploy/personal-18plus/caretaker/caretaker.py /opt/fluxer-caretaker/caretaker.py
   sudo python3 /opt/fluxer-caretaker/caretaker.py apply-settings
   ```
5. **Contact address:** the pages give `admin@porchlite.xyz`. To receive it for free, open **Email**, then **Email Routing**, in Cloudflare for porchlite.xyz, turn it on, and forward `admin@` to your own inbox.

To change the wording later, edit the Markdown files and push to `main`; the site updates within a minute or two.

## Moving from Z's Place to Porchlite

If you already installed under zsplace.site, these steps switch everything over. If you haven't installed yet, just use `porchlite.xyz` in step 4 above and skip this.

1. **DNS:** at your domain registrar, add an **A record** for `porchlite.xyz` (host `@`) pointing at your server's IP. Wait until `ping porchlite.xyz` shows that IP.
2. **Get the new kit on the server:**
   ```sh
   cd ~/fluxer && git pull
   ```
3. **Move Fluxer to the new domain** (it gets a new HTTPS certificate on its own):
   ```sh
   sudo rexctl config set domain porchlite.xyz
   ```
   Passkeys made on the old domain stop working; passwords are fine.
4. **Update the bot settings** to the new name, address and colour:
   ```sh
   sudo sed -i -e 's#zsplace.site#porchlite.xyz#g' -e "s#Z's Place#Porchlite#g" \
     -e 's#^BRAND_COLOR=.*#BRAND_COLOR=\#D9A95B#' /etc/fluxer-caretaker.env
   ```
5. **Apply the look:** this sets the name, amber colour, lantern logo and icon, the Porchlite site theme and the badges.
   ```sh
   cd ~/fluxer/deploy/personal-18plus && sudo sh install-bots.sh
   ```
6. **Sign-in background (optional):** in `https://porchlite.xyz/admin`, open **Branding** and upload `branding/porchlite-backdrop.jpg` as the sign-in backdrop.
7. **Old address:** keep `zsplace.site` pointing at the server until people have moved over, or let it lapse.

**Cottage theme (Nov 2026):** Porchlite now has a cottagecore look: "dusk garden" in Dark mode and "morning cottage" in Light mode, with honey `#D9A95B` as the brand colour. Members can still choose their own theme in Appearance. If you installed before this, run:
```sh
cd ~/fluxer && git pull
sudo sed -i 's/^BRAND_COLOR=.*/BRAND_COLOR=#D9A95B/' /etc/fluxer-caretaker.env
cd deploy/personal-18plus && sudo sh install-bots.sh
```

The site theme is `branding/porchlite-theme.css`. It recolours all of Fluxer's colours for Dark, Coal (both get dusk garden) and Light (morning cottage). It's about 30 KB; Fluxer's limit for custom CSS is 32 KB. To change it, edit that file and run `sudo sh install-bots.sh` again; to remove it, delete `/opt/fluxer-caretaker/theme.css` and clear the **Custom CSS** box in `/admin` Branding.

## Files here

| File | Purpose |
| --- | --- |
| `setup-server.sh` | Step 1: hardens a fresh server and installs Fluxer with sign-up approval |
| `install-bots.sh` | Step 2: installs the bots, schedules updates and backups, applies 18+ settings |
| `caretaker/caretaker.py` | The bots (Python standard library only) |
| `caretaker/caretaker.env.example` | Settings for the bots |
| `caretaker/offsite-backup.sh` | Daily copy of backups to cloud storage with rclone |
| `branding/porchlite-theme.css` | Site theme (custom CSS) applied by `apply-settings` |
| `branding/badges/` | Profile badge images used by the badge bot |
| `branding/levels/` | Server-level badge images (Porch Light, Cozy Cottage, Moonlit Garden) |
| `systemd/` | Timers that run the bots |
| `legal/` | Rules, terms and privacy templates |

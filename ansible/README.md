# Fleet management

Ansible controls the robot fleet from a control node (the Pi 3), which runs
[Semaphore UI](https://semaphoreui.com) so deploys can be triggered from a
browser — no terminal needed on a machine that can't run one.

```
Mac / any browser  --https-->  Pi 3 (Semaphore UI + Ansible)  --SSH-->  robot1..N (Pi 4/5)
```

Each robot pulls `main` directly from GitHub (see `playbooks/deploy.yml`) —
the control node doesn't need its own checkout of the app code, just this
`ansible/` directory.

## One-time setup on the Pi 3

1. Install Docker on the Pi 3 (same as any robot — see `../install.sh` steps
   1–4, or `curl -fsSL https://get.docker.com | sh`).
2. Clone this repo (or at minimum `ansible/`) onto the Pi 3.
3. Generate the SSH keypair `inventory.yml` expects:
   ```
   ssh-keygen -t ed25519 -f ~/.ssh/redwing_key -C "fleet-control"
   ```
4. Copy `~/.ssh/redwing_key.pub` to each robot's `pi` user, e.g.:
   ```
   ssh-copy-id -i ~/.ssh/redwing_key.pub pi@robot1.local
   ```
   (repeat per robot — one-time, until you add new ones)
5. Bring up Semaphore:
   ```
   cd ansible/semaphore
   cp .env.example .env
   # edit .env: set SEMAPHORE_ADMIN_PASSWORD and generate
   # SEMAPHORE_ACCESS_KEY_ENCRYPTION with: head -c32 /dev/urandom | base64
   docker compose up -d
   ```
6. Open `http://<pi3-hostname-or-ip>:3000` and log in with the admin
   credentials from `.env`.

## One-time setup inside Semaphore's web UI

Semaphore's UI changes cosmetically between versions, but the shape is
always: a **Project**, containing a **Key Store** entry, a **Repository**, an
**Inventory**, and a **Template** that ties them together.

1. **Project** → New Project (e.g. "Redwing Fleet").
2. **Key Store** → New Key:
   - Type: SSH Key
   - Paste the contents of `~/.ssh/redwing_key` (the private key generated
     above) — this is what lets Semaphore reach the robots.
3. **Repository** → New Repository:
   - URL: `https://github.com/RiversEngineering/redwing`
   - Branch: `main`
   - Access Key: None (the repo is public, cloned over plain HTTPS — the SSH
     key above is only for reaching the robots, not for cloning)
   - Semaphore installs `../requirements.yml`'s collections (`community.docker`,
     `community.general`) automatically before each run.
4. **Inventory** → New Inventory:
   - Type: File, pointing at `ansible/inventory.yml` in the repository above
   - User Credentials: the SSH key from step 2
5. **Template** → New Template, named e.g. "Deploy":
   - Playbook: `ansible/playbooks/deploy.yml`
   - Inventory / Repository: the ones created above
   - Under **Ansible Prompts**, check **Limit** — this adds a "Limit" field
     to the run dialog so you can target one host at a time.
   - Save, then **Run** — this is the button you'll use from now on instead
     of a terminal.
6. **Template** → New Template again, named e.g. "Restore Workspace":
   - Playbook: `ansible/playbooks/restore.yml`
   - Same Inventory / Repository as above
   - Also enable the **Limit** prompt here — this one wipes a robot's student
     workspace, so you always want to target it at one specific robot, never
     the whole fleet at once.
7. **Template** → New Template, named e.g. "Flash Firmware":
   - Playbook: `ansible/playbooks/flash_firmware.yml`
   - Same Inventory / Repository as above
   - Enable the **Limit** prompt.
   - Pulls latest `main` (so a new `firmware/redwing.uf2` is on disk even if
     you haven't run Deploy since pushing it), then calls the daemon's
     `/flash_firmware` endpoint — the same picotool sequence the dashboard's
     Firmware tab uses, just triggered over HTTP instead of a click.
   - Requires each robot's daemon container to already have this endpoint —
     i.e. run "Deploy" at least once after this feature was added before
     "Flash Firmware" will work on a given robot; otherwise the call 404s
     against the still-running old container.
8. **Template** → New Template, named e.g. "Power Off Fleet":
   - Playbook: `ansible/playbooks/shutdown.yml`
   - Same Inventory / Repository as above
   - Leave **Limit** empty by default (or enable the prompt if you also want
     the option to power off just one robot) — this one's meant to hit the
     whole fleet.

Two separate templates on purpose (Deploy vs. Restore): `restore.yml` used to be a second,
`restore`-tagged play bolted onto the bottom of `deploy.yml`, but Ansible
runs every play by default unless you explicitly filter tags — so a plain
"Run" on the old combined file would deploy *and* immediately wipe every
robot's workspace in the same task. Splitting them into separate playbooks
(and separate Templates) makes that structurally impossible instead of
relying on remembering to pass the right flag every time.

**To test a change on one robot before rolling it out to the fleet**: run
the "Deploy" template, type that robot's inventory name (e.g. `robot5`) into
the Limit field, and check the log. Once it looks right, run it again with
the Limit field empty to hit the whole fleet.

## Scheduling automatic shutdown

To catch a robot a student left powered on (draining its battery), schedule
the "Power Off Fleet" template to run automatically instead of relying on
someone remembering to click it:

1. Open the "Power Off Fleet" template → **Schedules** tab → New Schedule.
2. Cron expression for 6pm daily: `0 18 * * *`
3. Leave Limit empty so it hits every robot.

Semaphore's scheduler defaults to **UTC**, not your local time — a `6 18`
schedule would otherwise fire at 6pm UTC (2pm Eastern), not 6pm locally.
`ansible/semaphore/docker-compose.yml` sets `SEMAPHORE_SCHEDULE_TIMEZONE` to
`America/New_York` to handle this; override it in `.env` if that's the wrong
zone. A powered-off robot won't respond to the next scheduled Deploy either —
that's expected, not a failure — it'll just pick up whatever's latest the
next time someone turns it on and runs Deploy (or its own next scheduled
power-off, unaffected either way).

## Adding a new robot

1. Image it (Raspberry Pi Imager, or `install.sh` for first boot).
2. `./add-robot.sh <new-robot-ip-or-hostname>` — trusts it with the fleet SSH
   key (equivalent to `ssh-copy-id -i ~/.ssh/redwing_key.pub pi@<host>`, with
   a reminder printed for step 3). Optionally alias it for a shorter command:
   ```
   echo 'alias add-robot="~/redwing/ansible/add-robot.sh"' >> ~/.bashrc
   source ~/.bashrc
   ```
3. Add it to `inventory.yml` — either edit the file directly on GitHub, or
   edit it on the Pi 3 and `git push`. Semaphore always re-clones fresh from
   GitHub on every run, so either way works the same; nothing needs pushing
   *to* the Pi 3 itself.
4. Commit/push (if not already) — future deploys pick it up automatically.
5. Run the "Deploy" template with **Limit** set to the new robot's name to
   verify it before including it in a fleet-wide run.

## Known gap

`playbooks/deploy.yml`'s "Create workspace directory" task creates
`/home/pi/workspace` on each robot, but `docker-compose.yml` actually stores
student work in the `student_workspace` **named Docker volume**, not a bind
mount to that path — so that directory currently isn't used by anything.
Left as-is here since it's unrelated to the fleet-control changes above, but
worth cleaning up separately.

## Security notes

- `ansible.cfg` (repo root) sets `host_key_checking = False` so first-contact
  SSH to a freshly imaged or re-imaged robot doesn't hang on an interactive
  prompt Semaphore can't answer. This is standard for a closed classroom LAN
  of known devices, but it does mean Ansible won't warn you if a robot's host
  key unexpectedly changes.
- Don't expose Semaphore's port 3000 to the open internet. If you want to
  trigger deploys from off the school network, put the Pi 3 on a private mesh
  (e.g. Tailscale) instead of port-forwarding.

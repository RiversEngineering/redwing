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
   - Semaphore installs `../requirements.yml`'s collections (`community.docker`)
     automatically before each run.
4. **Inventory** → New Inventory:
   - Type: File, pointing at `ansible/inventory.yml` in the repository above
   - User Credentials: the SSH key from step 2
5. **Template** → New Template:
   - Playbook: `ansible/playbooks/deploy.yml`
   - Inventory / Repository: the ones created above
   - Save, then **Run** — this is the button you'll use from now on instead
     of a terminal.

Test against one robot first (Semaphore lets you pass `--limit robot1` as an
extra CLI arg on a template, matching the comment at the top of
`playbooks/deploy.yml`) before running the fleet-wide template.

## Adding a new robot

1. Image it (Raspberry Pi Imager, or `install.sh` for first boot).
2. `./add-robot.sh <new-robot-ip-or-hostname>` — trusts it with the fleet SSH
   key (equivalent to `ssh-copy-id -i ~/.ssh/redwing_key.pub pi@<host>`, with
   a reminder printed for step 3).
3. Add it to `inventory.yml`.
4. Commit/push — future deploys pick it up automatically.

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

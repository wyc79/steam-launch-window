# Running the history backfill on a server

The backfill needs one request per game (about 58,000 requests, roughly
16 hours at 1 per second). An always-on Linux box such as a Raspberry Pi is
a good place for it. Needs Python 3.11+ and git.

## 1. Get the code

```bash
cd ~
git clone https://github.com/wyc79/steam-launch-window.git
cd steam-launch-window
git checkout phase-1   # until it is merged to main
```

## 2. Bring over the progress so far (optional)

If a backfill already ran elsewhere, stop it there (Ctrl+C saves), then copy
its `games.csv` so the server continues instead of starting over:

```bash
mkdir -p ~/steam-launch-window/_data/history
# from the other machine:
scp _data/history/games.csv pi@<server>:steam-launch-window/_data/history/
```

Without this file the script first lists all games since 2022 (about 5 minutes),
then fills the counts.

## 3. Start it as a service

```bash
chmod +x scripts/server/run_history_backfill.sh
mkdir -p ~/.config/systemd/user
cp scripts/server/steam-history-backfill.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now steam-history-backfill
sudo loginctl enable-linger "$USER"   # keep it running after logout and across reboots
```

The service file assumes the repo is at `~/steam-launch-window`. Edit
`ExecStart` if it is somewhere else.

## 4. Watch it

```bash
journalctl --user -u steam-history-backfill -f          # live log
grep -c ',api,\|,zero_total,' _data/history/games.csv   # rows done
```

It logs a progress line every 200 games and stops by itself when every game
has a count ("backfill complete").

## 5. When it is done

Copy `_data/history/games.csv` back to the machine that commits the data branch, or
commit it from the server if it has the data branch checked out. Then remove the service:

```bash
systemctl --user disable --now steam-history-backfill
```

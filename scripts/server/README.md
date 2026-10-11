# Long one-off jobs on a server

Two jobs are too long for GitHub Actions or a laptop. They run once on an
always-on Linux box (e.g. a Raspberry Pi); after that, Actions only do the
small daily and weekly increments.

| Job | Requests | Time | Service |
|---|---|---|---|
| History backfill: 30-day review counts and the hidden Early Access check | about 70,000 | about 20 h at 1/s | `steam-history-backfill` |
| First follower scrape: about 11,000 tracked games | about 11,000 | about 15 h at 1 per 5 s | `steam-follower-scrape` |

They use different Steam hosts, so they can run at the same time.
Both need Python 3.11+ and git.

## 1. Get the code

```bash
cd ~
git clone https://github.com/wyc79/steam-launch-window.git
cd steam-launch-window
```

Already cloned? `git checkout main && git pull`.

## 2. History backfill

To continue a backfill started elsewhere, stop it there (Ctrl+C saves),
then copy its `games.csv` over first:

```bash
mkdir -p ~/steam-launch-window/_data/history
# from the other machine:
scp _data/history/games.csv <user>@<server>:steam-launch-window/_data/history/
```

Without that file the script first lists all games since 2022 (about 5 minutes).

```bash
cd ~/steam-launch-window
mkdir -p ~/.config/systemd/user
cp scripts/server/steam-history-backfill.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now steam-history-backfill
```

It stops by itself when every game is done ("backfill complete").

## 3. First follower scrape

The script takes the newest upcoming snapshot from the `data` branch, then
fetches follower counts one request every 5 seconds. steamcommunity.com blocks
for a long time after a 429, so the first 429 stops the run and the script
waits an hour before trying again. While blocked, it makes about one request
an hour.

```bash
cd ~/steam-launch-window
cp scripts/server/steam-follower-scrape.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now steam-follower-scrape
```

To change the rate, edit `Environment=COMMUNITY_INTERVAL=5` in
`~/.config/systemd/user/steam-follower-scrape.service`, then run
`systemctl --user daemon-reload && systemctl --user restart steam-follower-scrape`.
It stops by itself when every tracked game has a count ("follower scrape complete").

## Keep them running after logout and reboots

```bash
sudo loginctl enable-linger "$USER"
```

## Watch them

```bash
systemctl --user status steam-history-backfill steam-follower-scrape --no-pager
sudo journalctl _SYSTEMD_USER_UNIT=steam-history-backfill.service -f
sudo journalctl _SYSTEMD_USER_UNIT=steam-follower-scrape.service -f
```

On Raspberry Pi OS your user may not be able to read its own journal;
`sudo` (as above) or `sudo usermod -aG systemd-journal $USER` fixes that.

## When they are done

Copy the results back to the machine that commits the data branch:

```bash
scp <user>@<server>:steam-launch-window/_data/history/games.csv _data/history/
scp -r <user>@<server>:steam-launch-window/_data/followers _data/
```

Then remove the services:

```bash
systemctl --user disable --now steam-history-backfill steam-follower-scrape
```

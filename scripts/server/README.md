# Long one-off jobs on a server

Two jobs are too long for GitHub Actions or a laptop. They run once on an
always-on Linux box (e.g. a Raspberry Pi); after that, Actions only do the
small daily and weekly increments.

| Job | Requests | Time | Service |
|---|---|---|---|
| History backfill: 30-day review counts and the hidden Early Access check | about 70,000 | about 20 h at 1/s | `steam-history-backfill` |
| Optional: first-day and first-week review counts for all launches since 2022 | about 100,000 | about 2 to 3 days | none, a one-off command (section 4) |
| ~~First follower scrape~~ | retired 2026-10-11 | | `steam-follower-scrape` |

The follower scrape is retired: steamcommunity.com blocked the IP for 8+ hours
after about 60 requests. Followers now come from Games Popularity in the daily
GitHub Actions job, which does not use this box. Do not request steamcommunity.com
from this network while the block may still be on.
Both jobs need Python 3.11+ and git.

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

## 3. First follower scrape (retired)

Kept for reference only. `run_follower_scrape.sh` and its service still work,
but do not start them: the community site blocks this IP for many hours.

## 4. Optional: first-day and first-week review counts

After the history backfill is merged and this box runs the current `main`, this
fills `reviews_1d` and `reviews_7d` for every launch since 2022 (two requests per
game with any reviews in its first 30 days; games with none get 0 without a request):

```bash
cd ~/steam-launch-window && git pull
.venv/bin/python -m pipeline.collect_history --skip-listing --early-since 2022-01-01   --budget-minutes 1440 --fail-if-incomplete
```

Rerun it until it exits with 0. Then copy `history/games.csv` back as in "When they are done".

## Keep them running after logout and reboots

```bash
sudo loginctl enable-linger "$USER"
```

## Watch them

```bash
systemctl --user status steam-history-backfill --no-pager
sudo journalctl _SYSTEMD_USER_UNIT=steam-history-backfill.service -f
```

On Raspberry Pi OS your user may not be able to read its own journal;
`sudo` (as above) or `sudo usermod -aG systemd-journal $USER` fixes that.

## When they are done

Copy the results back to the machine that commits the data branch:

```bash
scp <user>@<server>:steam-launch-window/_data/history/games.csv _data/history/
```

Then remove the service:

```bash
systemctl --user disable --now steam-history-backfill
```

# Demo video

A 44-second demo of the live site and the Hugging Face dataset, with Simplified Chinese
subtitles, for Chinese indie developers. Nothing here touches `site/`: it records the
deployed site at <https://wyc79.github.io/steam-launch-window/>.

Output, in `out/`:

- `steam-launch-window-demo.mp4`: 3840×2160 (4K), H.264 High@5.2, 60 fps, BT.709, with the background music (AAC, 192 kb/s)
- `subtitles.srt`: the same subtitles as a file, for players and upload pages that take one
- `cover.png` (1920×1080) and `cover-4x3.png` (1440×1080): the video cover, from `npm run cover`

## Make it again

Needs Node 18+ and `ffmpeg` on the `PATH` (any build with `libx264`; `libass` is not needed).

```bash
cd video
npm ci
npm run setup      # Playwright's Chromium, once
npm run record     # about 2 minutes
node compose.mjs --music music/ElevenLabs_steam-launch-window-video.wav   # about 3.5 minutes
```

The music (ElevenLabs Music v2.5, made to the video's length) is kept in `music/`, which
git ignores. Without `--music` the video gets a silent track.

The video shows whatever the site and the dataset page show on the day it is recorded.
The subtitles name no numbers, so they stay true when the data changes.

The two steps can run on their own:

```bash
node record.mjs            # all three clips into build/clips/, timings into build/timeline.json
node record.mjs site       # one clip again: site, dataset, end or credits
node compose.mjs           # out/ from what is in build/
node compose.mjs --music track.wav   # with background music
```

## What it shows

| Time | Clip | Subtitle |
|---|---|---|
| 0–4 s | the site as it opens | Steam 游戏什么时候发售比较合适？ |
| 4–10 s | scroll to 未来竞争: the next 13 weeks, with Steam sales and Next Fest | 看看未来 13 周的 Steam 发售档期 |
| 10–16 s | type `Rogue`, pick 类 Rogue; type 像素, pick 像素图形; a row per tag appears | 输入游戏标签，看看同类游戏的竞争情况 |
| 16–23 s | open a week: its count box, then the week's games and the niche's most anticipated | 点开一周，查看当周发售的同类游戏 |
| 23–29 s | scroll to 历史表现 | 以及同类游戏过往的发售表现 |
| 29–37 s | the dataset card on Hugging Face, then its "What is here" table | 背后的数据集也已在 Hugging Face 公开 |
| 37–41 s | end card: Steam 发售窗口, site address, dataset (in Chinese) | — |
| 41–44 s | credits: Claude Opus 5.5 for the project and video script, ElevenLabs Music v2.5 for the music | — |

## Cover

`npm run cover` (about 20 seconds) opens the site, picks the same tags as the video, takes a
screenshot of the competition table and puts it under the title in `cover.html`. The text
is `COVER` in `config.mjs`. Everything sits in one 1320px column, so the same page is drawn
at 16:9 and at 4:3, for upload pages (such as Bilibili's) that ask for both.

## Changing it

- Wording, tags, which week opens, the end card, the credits and the transitions: `config.mjs`.
- Order, pauses and scroll speed: `record.mjs`. `clip.start("name")` and `clip.end()` mark
  when a subtitle shows, so its timing follows the footage when pauses change.
- Subtitle look and position: `compose.mjs`. Card looks: `endcard.html`, `credits.html`.
- Music level: `MUSIC` in `config.mjs`. The track is measured and raised or lowered by one
  fixed gain to that loudness (−20 LUFS), with no compression; it plays once, with a 1.5 s
  fade at the end.

`record.mjs` stops with an error rather than recording something wrong: when typing a tag
no longer offers the expected tag first, when the week column or the dataset card's
"What is here" heading is missing, or when the site has not finished drawing in 60 seconds.

## How it records

Playwright's own video recording drops frames when scrolling. Here every frame is a
screenshot taken after the page is put in that frame's state (`lib/clip.mjs`): a scroll is
one screenshot per frame along an eased path, and a pause is one screenshot repeated. So
scrolling is smooth however slow the machine is, and runs are repeatable. Screenshots
never show a cursor, and clicks on the table are DOM clicks, so no hover state is left behind.

- The page is 1600×900 CSS pixels drawn at 2.4× scale, so frames are a native 3840×2160
  (not upscaled), and the site's text is 20% larger than in a 1920-wide window, with the
  same desktop layout. For 1080p, set `VIDEO` in `config.mjs` to 1920×1080 and record
  again; subtitles and cards scale with it.
- The site is in Chinese (its own language setting) and in its light theme.
- It waits until no section is `aria-busy` before recording, and again after each tag.
- Clicking a week focuses its cell, which nudges the page; the recorder puts the page back
  where it was, then scrolls once. The count box that a click opens is shown for a moment,
  then closed with Escape, as the site allows.
- Requests to Google Analytics are blocked, so recording runs do not count as visits.
- Clips are stored lossless in RGB; `compose.mjs` keeps the whole filter graph in RGB and
  converts to BT.709 YUV once, at the end, so colours match the site (paper `#F2F0E9`).
- Subtitles are drawn by Chromium as transparent PNGs (PingFang SC, falling back to Noto
  Sans SC) and laid over the footage with a short fade, since this ffmpeg needs no libass.

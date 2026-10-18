// Joins the recorded clips (build/timeline.json) into the final video: cross-fades
// between clips, Chinese subtitles drawn as images and laid over the footage, and
// the same subtitles as an .srt file.
//
//   node compose.mjs                      out/steam-launch-window-demo.mp4 + out/subtitles.srt
//   node compose.mjs --music track.mp3    with quiet background music

import { spawn } from "node:child_process";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright";
import { SUBTITLES, TRANSITIONS } from "./config.mjs";

const here = (p) => fileURLToPath(new URL(p, import.meta.url));
const BUILD = here("build/");
const OUT = here("out/");
const ORDER = ["site", "dataset", "end", "credits"];
const FADE = 0.25; // subtitle fade in and out
const GAP = 0.2; // between two subtitles that would otherwise touch
const BOTTOM = 64; // subtitle box's distance from the bottom edge, in 1080p pixels

const args = process.argv.slice(2);
const music = args.includes("--music") ? args[args.indexOf("--music") + 1] : null;

const timeline = JSON.parse(await readFile(`${BUILD}timeline.json`, "utf8"));
const H = timeline.size.height;
const k = H / 1080; // subtitles are styled for 1080p and drawn k times larger
const clips = ORDER.map((name) => {
  const clip = timeline.clips[name];
  if (!clip) throw new Error(`clip ${name} is not recorded; run node record.mjs ${name}`);
  return { name, ...clip };
});

// where each clip starts in the final video (a cross-fade overlaps it with the last)
let total = 0;
for (const [i, clip] of clips.entries()) {
  clip.fade = i === 0 ? 0 : TRANSITIONS[`${clips[i - 1].name}→${clip.name}`] ?? 0;
  clip.offset = total - clip.fade;
  total = clip.offset + clip.seconds;
}

// subtitles on the final video's clock
const cues = clips
  .flatMap((clip) => clip.cues.map((c) => ({ ...c, start: c.start + clip.offset, end: c.end + clip.offset })))
  .filter((c) => SUBTITLES[c.name])
  .sort((a, b) => a.start - b.start);
for (let i = 1; i < cues.length; i++) {
  const [a, b] = [cues[i - 1], cues[i]];
  if (b.start - a.end < GAP) {
    const mid = (a.end + b.start) / 2;
    a.end = mid - GAP / 2;
    b.start = mid + GAP / 2;
  }
}

// each subtitle as a transparent PNG, drawn by Chromium for good Chinese type
await mkdir(`${BUILD}subs`, { recursive: true });
await mkdir(OUT, { recursive: true });
const browser = await chromium.launch();
try {
  const page = await browser.newPage({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: k });
  for (const [i, cue] of cues.entries()) {
    await page.setContent(`<!doctype html><meta charset="utf-8">
      <style>
        html, body { margin: 0; background: transparent; }
        body { display: flex; justify-content: center; padding-top: 40px; }
        .sub {
          font-family: "PingFang SC", "Noto Sans SC", "Microsoft YaHei", sans-serif;
          font-size: 36px; font-weight: 500; line-height: 1.3; letter-spacing: 0.04em;
          color: #fff; background: rgba(17, 17, 17, 0.78);
          padding: 12px 30px 13px; border-radius: 8px;
          text-shadow: 0 1px 2px rgba(0, 0, 0, 0.35);
        }
      </style>
      <div class="sub"></div>`);
    await page.locator(".sub").evaluate((el, text) => (el.textContent = text), SUBTITLES[cue.name]);
    await page.evaluate(() => document.fonts.ready);
    cue.png = `${BUILD}subs/${i}-${cue.name}.png`;
    await page.locator(".sub").screenshot({ path: cue.png, omitBackground: true });
  }
} finally {
  await browser.close();
}

// the .srt
const stamp = (t) => {
  const ms = Math.round(t * 1000);
  const p = (n, w = 2) => String(n).padStart(w, "0");
  return `${p(Math.floor(ms / 3_600_000))}:${p(Math.floor(ms / 60_000) % 60)}:${p(Math.floor(ms / 1000) % 60)},${p(ms % 1000, 3)}`;
};
const srt = cues.map((c, i) => `${i + 1}\n${stamp(c.start)} --> ${stamp(c.end)}\n${SUBTITLES[c.name]}\n`).join("\n");
await writeFile(`${OUT}subtitles.srt`, srt);

// the ffmpeg graph: clips cross-faded in turn, then each subtitle faded in and out on top
const inputs = [];
const graph = [];
// one time base for all clips, so a cut (concat) can be followed by a cross-fade
for (const [i, clip] of clips.entries()) {
  inputs.push("-i", `${BUILD}${clip.file}`);
  graph.push(`[${i}:v]settb=AVTB,setpts=PTS-STARTPTS[c${i}]`);
}
let video = "c0";
for (let i = 1; i < clips.length; i++) {
  const { fade, offset } = clips[i];
  graph.push(
    fade > 0
      ? `[${video}][c${i}]xfade=transition=fade:duration=${fade}:offset=${offset.toFixed(4)}[x${i}]`
      : `[${video}][c${i}]concat=n=2:v=1:a=0[x${i}]`,
  );
  video = `x${i}`;
}
for (const [i, cue] of cues.entries()) {
  const n = clips.length + i;
  const len = cue.end - cue.start;
  inputs.push("-loop", "1", "-framerate", String(timeline.fps), "-t", len.toFixed(4), "-i", cue.png);
  graph.push(
    `[${n}:v]format=rgba,fade=t=in:st=0:d=${FADE}:alpha=1,fade=t=out:st=${(len - FADE).toFixed(4)}:d=${FADE}:alpha=1,` +
      `setpts=PTS-STARTPTS+${cue.start.toFixed(4)}/TB[s${i}]`,
    `[${video}][s${i}]overlay=x=(W-w)/2:y=H-h-${Math.round(BOTTOM * k)}:format=gbrp:eof_action=pass:enable='between(t,${cue.start.toFixed(4)},${cue.end.toFixed(4)})'[o${i}]`,
  );
  video = `o${i}`;
}
graph.push(`[${video}]scale=out_color_matrix=bt709:out_range=tv,format=yuv420p[v]`);

if (music) {
  inputs.push("-stream_loop", "-1", "-i", music);
  graph.push(`[${clips.length + cues.length}:a]volume=0.18,afade=t=in:d=1.5,afade=t=out:st=${(total - 2.5).toFixed(3)}:d=2.5,atrim=0:${total.toFixed(3)}[a]`);
} else {
  inputs.push("-f", "lavfi", "-t", total.toFixed(3), "-i", "anullsrc=channel_layout=stereo:sample_rate=48000");
}

const file = `${OUT}steam-launch-window-demo.mp4`;
const ffmpeg = [
  "-y", "-loglevel", "error",
  ...inputs,
  "-filter_complex", graph.join(";\n"),
  "-map", "[v]", "-map", music ? "[a]" : `${clips.length + cues.length}:a`,
  "-c:v", "libx264", "-preset", "slow", "-crf", "16", "-profile:v", "high", "-pix_fmt", "yuv420p",
  "-r", String(timeline.fps), "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709",
  "-c:a", "aac", "-b:a", "128k", "-t", total.toFixed(3), "-movflags", "+faststart",
  file,
];
await writeFile(`${BUILD}ffmpeg-args.json`, JSON.stringify(ffmpeg, null, 1));
await new Promise((resolve, reject) => {
  const p = spawn("ffmpeg", ffmpeg, { stdio: "inherit" });
  p.on("error", reject);
  p.on("close", (code) => (code === 0 ? resolve() : reject(new Error(`ffmpeg exited with ${code}`))));
});

console.log(`\n${file}: ${total.toFixed(2)} s`);
for (const c of cues) console.log(`  ${c.start.toFixed(2)}–${c.end.toFixed(2)}  ${SUBTITLES[c.name]}`);

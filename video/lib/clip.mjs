// Deterministic frame capture. Every video frame is a screenshot taken after the
// page has been put in the state that frame shows, so scrolling is smooth however
// slow the screenshots are. A still stretch is one screenshot written many times.
// Frames go straight into ffmpeg as PNGs and come out as a lossless RGB clip.

import { spawn } from "node:child_process";

const easeInOut = (t) => (t < 0.5 ? 4 * t * t * t : 1 - (-2 * t + 2) ** 3 / 2);

export class Clip {
  constructor(page, file, fps) {
    this.page = page;
    this.file = file;
    this.fps = fps;
    this.frames = 0;
    this.cues = [];
    this.open = null;
    this.last = null;
    this.ffmpeg = spawn(
      "ffmpeg",
      ["-y", "-loglevel", "error", "-f", "image2pipe", "-c:v", "png", "-framerate", String(fps), "-i", "-",
        "-c:v", "libx264rgb", "-qp", "0", "-preset", "ultrafast", "-r", String(fps), file],
      { stdio: ["pipe", "inherit", "inherit"] },
    );
    this.done = new Promise((resolve, reject) => {
      this.ffmpeg.on("error", reject);
      this.ffmpeg.on("close", (code) => (code === 0 ? resolve() : reject(new Error(`ffmpeg exited with ${code} for ${file}`))));
    });
  }

  get seconds() {
    return this.frames / this.fps;
  }

  // wait until the page has drawn its latest change
  async settle() {
    await this.page.evaluate(() => new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r))));
  }

  async snap() {
    await this.settle();
    this.last = await this.page.screenshot({ type: "png", animations: "disabled", caret: "initial" });
  }

  async write(n = 1) {
    for (let i = 0; i < n; i++) {
      if (!this.ffmpeg.stdin.write(this.last)) await new Promise((r) => this.ffmpeg.stdin.once("drain", r));
      this.frames++;
    }
  }

  // the current state, held for `seconds`
  async hold(seconds) {
    await this.snap();
    await this.write(Math.max(1, Math.round(seconds * this.fps)));
  }

  // eased scroll to `y` (CSS pixels) over `seconds`, one screenshot per frame
  async scrollTo(y, seconds) {
    const from = await this.page.evaluate(() => window.scrollY);
    const to = await this.page.evaluate(
      (y) => Math.max(0, Math.min(y, document.documentElement.scrollHeight - innerHeight)),
      y,
    );
    const n = Math.max(1, Math.round(seconds * this.fps));
    for (let i = 1; i <= n; i++) {
      const top = from + (to - from) * easeInOut(i / n);
      await this.page.evaluate((top) => window.scrollTo({ top, behavior: "instant" }), top);
      await this.snap();
      await this.write();
    }
  }

  // type text one key at a time, as a person would
  async type(text, perKey = 0.11) {
    for (const ch of text) {
      await this.page.keyboard.type(ch);
      await this.hold(perKey);
    }
  }

  // subtitle cues: start(name) ... end(); times are this clip's seconds
  start(name) {
    if (this.open) this.end();
    this.open = { name, start: this.seconds };
  }

  end() {
    if (!this.open) return;
    this.cues.push({ ...this.open, end: this.seconds });
    this.open = null;
  }

  async close() {
    this.end();
    this.ffmpeg.stdin.end();
    await this.done;
    return { file: this.file, seconds: this.seconds, cues: this.cues };
  }
}

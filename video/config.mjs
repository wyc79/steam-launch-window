// Everything the video says and where it records from. Edit this file to change
// the wording or the pages; record.mjs decides when each line shows.

export const SITE_URL = "https://wyc79.github.io/steam-launch-window/";
export const DATASET_URL = "https://huggingface.co/datasets/strikeoo/steam-launch-data";
export const REPO_URL = "https://github.com/wyc79/steam-launch-window";

// The page is laid out at 1600x900 CSS pixels and drawn at the video's size, so
// 3840x2160 is a 2.4x screen (1920x1080 would be 1.2x). At 1600 wide the site keeps
// its desktop layout and its text is larger than in a 1920-wide window.
export const VIEWPORT = { width: 1600, height: 900 };
export const VIDEO = { width: 3840, height: 2160 };
export const SCALE = VIDEO.width / VIEWPORT.width;
export const FPS = 60;

// the two tags typed into the site's tag box
export const TAGS = [
  { type: "Rogue", pick: "类 Rogue" },
  { type: "像素", pick: "像素图形" },
];

// the week opened in the competition table: its column, counting this week as 0
export const WEEK = 3;

// Subtitles (Simplified Chinese), by the cue names record.mjs uses
export const SUBTITLES = {
  intro: "Steam 游戏什么时候发售比较合适？",
  calendar: "看看未来 13 周的 Steam 发售档期",
  tags: "输入游戏标签，看看同类游戏的竞争情况",
  week: "点开一周，查看当周发售的同类游戏",
  history: "以及同类游戏过往的发售表现",
  dataset: "背后的数据集也已在 Hugging Face 公开",
};

// the closing card
export const END_CARD = {
  title: "Steam 发售窗口",
  url: "wyc79.github.io/steam-launch-window/",
  dataset: "数据集已在 Hugging Face 公开",
  datasetUrl: "huggingface.co/datasets/strikeoo/steam-launch-data",
};

// the credits card after it: [what, who]
export const CREDITS = [
  ["项目开发与视频脚本", "Claude Opus 5.5"],
  ["背景音乐", "ElevenLabs Music v2.5"],
];

// how each clip gives way to the next, in seconds of cross-fade (0 = a plain cut)
export const TRANSITIONS = { "site→dataset": 0, "dataset→end": 0.5, "end→credits": 0.5 };

// Chinese names of the event series in data/events.yaml (the name without its year),
// for the Chinese page. "{year}" stands for the event's year. Steam's own Chinese names
// where its Chinese news posts or Steamworks' event schedule give one (checked
// 2026-10-15); the rest, marked "ours", follow Steam's pattern ("Steam ○○游戏节") and
// Steam's Chinese tag names. Big releases keep their English names.

export const EVENT_NAMES_ZH = {
  // seasonal sales
  "Steam Winter Sale": "{year} 年 Steam 冬季特卖",
  "Steam Lunar New Year Sale": "{year} 年 Steam 农历新年特卖",
  "Steam Spring Sale": "{year} 年 Steam 春季特卖",
  "Steam Summer Sale": "{year} 年 Steam 夏日特卖",
  "Steam Autumn Sale": "{year} 年 Steam 秋季特卖",

  // Next Fest
  "Steam Next Fest February": "Steam 新品节：{year} 年 2 月版",
  "Steam Next Fest June": "Steam 新品节：{year} 年 6 月版",
  "Steam Next Fest October": "Steam 新品节：{year} 年 10 月版",

  // themed fests
  "Steam (Combat) PvP Fest": "{year} 年 Steam 玩家对战游戏节", // ours
  "Steam 4X Fest": "{year} 年 Steam 4X 游戏节", // ours
  "Steam Animal Fest": "{year} 年 Steam 动物游戏节", // ours
  "Steam Auto-Battler RPG Fest": "{year} 年 Steam 自走棋角色扮演游戏节",
  "Steam Automation Fest": "{year} 年 Steam 自动化游戏节", // ours
  "Steam Base Builder Fest": "{year} 年 Steam 基地建设游戏节",
  "Steam Bash Bash": "{year} 年 Steam 短兵激斗游戏节",
  "Steam Board Game Fest": "{year} 年 Steam 棋盘游戏节", // ours
  "Steam Box-Pushing Fest": "{year} 年 Steam 推箱子游戏节", // ours
  "Steam Bullet Fest": "{year} 年 Steam 弹幕射击游戏节", // ours
  "Steam Capitalism and Economy Fest": "{year} 年 Steam 资本主义与经济游戏节",
  "Steam City Builder and Colony Sim Fest": "{year} 年 Steam 城市营造与殖民模拟游戏节", // ours
  "Steam Cooking Fest": "{year} 年 Steam 烹饪游戏节",
  "Steam Couch Co-Op Fest": "{year} 年 Steam 沙发合作游戏节",
  "Steam Creature Collector Fest": "{year} 年 Steam 生物收集游戏节", // ours
  "Steam Cyberpunk Fest": "{year} 年 Steam 赛博朋克游戏节", // ours
  "Steam Deckbuilders Fest": "{year} 年 Steam 牌组构建游戏节",
  "Steam Desktop Companion Fest": "{year} 年 Steam 桌面伴侣游戏节",
  "Steam Detective Fest": "{year} 年 Steam 侦探游戏节", // ours
  "Steam Dinos vs. Robots Fest": "{year} 年 Steam 恐龙大战机器人游戏节",
  "Steam Endless Replayability Fest": "{year} 年 Steam 无限重玩游戏节",
  "Steam FPS Fest": "{year} 年 Steam FPS 游戏节",
  "Steam Farming Fest": "{year} 年 Steam 农场管理游戏节",
  "Steam Fighting Fest": "{year} 年 Steam 格斗游戏节",
  "Steam Fighting Games Fest": "{year} 年 Steam 格斗游戏节",
  "Steam Fishing Fest": "{year} 年 Steam 钓鱼游戏节", // ours
  "Steam Going Rogue Fest": "{year} 年 Steam 类 Rogue 游戏节", // ours
  "Steam Hidden Object Fest": "{year} 年 Steam 隐藏物体游戏节", // ours
  "Steam Horse Fest": "{year} 年 Steam 马匹游戏节", // ours
  "Steam House and Home Fest": "{year} 年 Steam 家园游戏节", // ours
  "Steam Idler Fest": "{year} 年 Steam 挂机游戏节", // ours
  "Steam JRPG Sale": "{year} 年 Steam 日系角色扮演游戏特卖",
  "Steam Medieval Fest": "{year} 年 Steam 中世纪游戏节",
  "Steam Mountaineering Fest": "{year} 年 Steam 登山游戏节",
  "Steam Mystery Fest": "{year} 年 Steam 悬疑游戏节",
  "Steam Ocean Fest": "{year} 年 Steam 海洋游戏节", // ours
  "Steam Open World Survival Crafting Fest": "{year} 年 Steam 开放世界生存制作游戏节",
  "Steam Party-Based RPG Fest": "{year} 年 Steam 团队角色扮演游戏节", // ours
  "Steam Pins and Pegs Fest": "{year} 年 Steam 弹球游戏节", // ours
  "Steam Pirates vs. Ninjas Fest": "{year} 年 Steam 海盗大战忍者游戏节",
  "Steam Planes, Trains, and Automobiles Fest": "{year} 年 Steam 飞机、火车和汽车游戏节",
  "Steam Political Sim Fest": "{year} 年 Steam 政治模拟游戏节", // ours
  "Steam Programming Fest": "{year} 年 Steam 编程游戏节", // ours
  "Steam Puzzle Fest": "{year} 年 Steam 解谜游戏节",
  "Steam PvE Survival Crafting Fest": "{year} 年 Steam PvE 生存制作游戏节", // ours
  "Steam Racing Fest": "{year} 年 Steam 竞速游戏节",
  "Steam Real-Time Strategy Fest": "{year} 年 Steam 即时战略游戏节",
  "Steam Remote Play Together Fest": "{year} 年 Steam 远程同乐游戏节",
  "Steam Remote Play Together Sale & Event": "{year} 年 Steam 远程同乐特卖及现场直播",
  "Steam Rhythm Fest": "{year} 年 Steam 节奏游戏节",
  "Steam SHMUP Fest": "{year} 年 Steam 清版射击游戏节",
  "Steam Scream Fest": "{year} 年 Steam 尖叫游戏节",
  "Steam Scream: The Revenge": "{year} 年 Steam 尖叫游戏节：复仇",
  "Steam Scream Fest 3": "{year} 年 Steam 尖叫游戏节 3",
  "Steam Scream 4 Fest": "{year} 年 Steam 尖叫游戏节 4", // ours
  "Steam Scream V Fest": "{year} 年 Steam 尖叫游戏节 V", // ours
  "Steam Sheep Fest": "{year} 年 Steam 绵羊游戏节",
  "Steam Shop Keeper Fest": "{year} 年 Steam 商店管理游戏节",
  "Steam Simfest Hobby Edition": "{year} 年 Steam 模拟游戏节：爱好版",
  "Steam Social Deduction Fest": "{year} 年 Steam 社交推理游戏节", // ours
  "Steam Space Exploration Fest": "{year} 年 Steam 太空探索游戏节",
  "Steam Sports Fest": "{year} 年 Steam 体育游戏节",
  "Steam Stealth Fest": "{year} 年 Steam 潜行游戏节",
  "Steam Strategy Fest": "{year} 年 Steam 策略游戏节",
  "Steam Survival Fest": "{year} 年 Steam 生存游戏节",
  "Steam TPS Fest": "{year} 年 Steam 第三人称射击游戏节", // ours
  "Steam Tower Defense Fest": "{year} 年 Steam 塔防游戏节",
  "Steam Train Fest": "{year} 年 Steam 火车游戏节", // ours
  "Steam Turn-Based RPG Fest": "{year} 年 Steam 回合制角色扮演游戏节",
  "Steam Typing Fest": "{year} 年 Steam 打字游戏节", // ours
  "Steam VR Fest": "{year} 年 Steam VR 游戏节",
  "Steam Visual Novel Fest": "{year} 年 Steam 视觉小说游戏节",
  "Steam Wargames Fest": "{year} 年 Steam 战争游戏节", // ours
  "Steam Witch Fest": "{year} 年 Steam 女巫游戏节",
  "Steam Zombies vs. Vampires Fest": "{year} 年 Steam 僵尸大战吸血鬼游戏节", // ours

  // holidays (the names the timing advice already uses)
  "China Spring Festival holiday": "{year} 年春节假期",
  "China National Day holiday": "{year} 年国庆节假期",
  "US Thanksgiving to Cyber Monday": "{year} 年美国感恩节至网络星期一",
  "Christmas to New Year": "{year} 年圣诞节至元旦",
};

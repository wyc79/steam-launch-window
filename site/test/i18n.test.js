import { describe, expect, test } from "vitest";

import * as copy from "../src/strings.js";


function shape(value) {
  if (typeof value === "function") return "function";
  if (!value || typeof value !== "object") return typeof value;
  return Object.fromEntries(Object.entries(value).map(([key, child]) => [key, shape(child)]));
}

describe("Chinese copy", () => {
  test("covers every string and formatter in the English bundle", () => {
    expect(copy.zh).toBeDefined();
    expect(shape(copy.zh)).toEqual(shape(copy.en));
  });

  test("uses Simplified Chinese for the public page identity and primary actions", () => {
    expect(copy.zh.title).toBe("Steam 发售窗口");
    expect(copy.zh.mast.methods).toBe("方法说明");
    expect(copy.zh.bar.tagPlaceholder).toBe("输入 Steam 标签");
    expect(copy.zh.methods.back).toBe("返回发售窗口");
  });

  test("starts the supported-language filter on the page's own language", () => {
    expect(copy.en.defaultLanguages).toEqual(["english"]);
    expect(copy.zh.defaultLanguages).toEqual(["schinese"]);
  });

  test("composes natural Chinese around dynamic groups and languages", () => {
    expect(copy.zh.sections.season.introFor("付费", copy.zh.sections.season.langs(["英语"]))).toBe(
      "根据过往年份支持英语的付费游戏发售数据，查看未来各周通常有多拥挤。",
    );
    expect(copy.zh.trends.of("2026 年第 1 季度", "20", "100", "付费", "20%")).toBe(
      "2026 年第 1 季度：100 款付费游戏发售中有 20 款（20%）",
    );
    expect(copy.zh.trends.summaryShare("付费", "支持英语", "10%", "10", "20%", "20", "2025 年")).toContain(
      "支持英语的付费游戏",
    );
  });
});

describe("language preference", () => {
  test("uses a saved choice before the browser's preferred languages", async () => {
    const language = await import("../src/language.js").catch(() => null);
    expect(language).not.toBeNull();
    expect(language.selectLanguage("en", ["zh-CN", "en-US"])).toBe("en");
  });

  test("uses the first supported browser language and otherwise falls back to English", async () => {
    const language = await import("../src/language.js").catch(() => null);
    expect(language).not.toBeNull();
    expect(language.selectLanguage(null, ["fr-FR", "zh-TW", "en-US"])).toBe("zh");
    expect(language.selectLanguage(null, ["fr-FR"])).toBe("en");
  });

  test("saves an explicit choice and reloads the current page", async () => {
    const language = await import("../src/language.js").catch(() => null);
    expect(language).not.toBeNull();
    const saved = [];
    let reloads = 0;
    language.changeLanguage("zh", {
      storage: { setItem: (key, value) => saved.push([key, value]) },
      location: { reload: () => (reloads += 1) },
    });
    expect(saved).toEqual([["yc-lang", "zh"]]);
    expect(reloads).toBe(1);
  });

  test("reads the saved choice when available and tolerates blocked storage", async () => {
    const { currentLanguage } = await import("../src/language.js");
    expect(currentLanguage({
      storage: { getItem: () => "zh" },
      navigator: { languages: ["en-US"] },
    })).toBe("zh");
    expect(currentLanguage({
      storage: { getItem: () => { throw new Error("blocked"); } },
      navigator: { languages: ["zh-CN"] },
    })).toBe("zh");
    expect(currentLanguage({
      storage: { getItem: () => null },
      navigator: { languages: [], language: "zh-CN" },
    })).toBe("zh");
  });

  test("still loads and switches when access to the storage property itself is blocked", async () => {
    const { changeLanguage, currentLanguage } = await import("../src/language.js");
    const previous = Object.getOwnPropertyDescriptor(globalThis, "localStorage");
    Object.defineProperty(globalThis, "localStorage", {
      configurable: true,
      get() { throw new Error("blocked"); },
    });
    let reloads = 0;
    try {
      expect(currentLanguage({ navigator: { languages: ["zh-CN"] } })).toBe("zh");
      changeLanguage("en", { location: { reload: () => (reloads += 1) } });
      expect(reloads).toBe(1);
    } finally {
      if (previous) Object.defineProperty(globalThis, "localStorage", previous);
      else delete globalThis.localStorage;
    }
  });

  test("selects the matching copy bundle", () => {
    expect(copy.stringsFor("en")).toBe(copy.en);
    expect(copy.stringsFor("zh")).toBe(copy.zh);
  });
});

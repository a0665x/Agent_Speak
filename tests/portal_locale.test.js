"use strict";

const assert = require("node:assert/strict");
const test = require("node:test");

const {
  DEFAULT_LOCALE,
  SUPPORTED_LOCALES,
  messages,
  resolveLocale,
  translate,
  withLocale,
} = require("../web/locale.js");

test("resolves query before storage and defaults invalid queries to English", () => {
  assert.equal(resolveLocale("?lang=ja", "zh-TW"), "ja");
  assert.equal(resolveLocale("", "ko"), "ko");
  assert.equal(resolveLocale("?lang=unsupported", "zh-TW"), "en");
  assert.equal(resolveLocale("", null), DEFAULT_LOCALE);
});

test("adds the selected locale to internal navigation", () => {
  assert.equal(withLocale("/docs", "ko"), "/docs?lang=ko");
  assert.equal(withLocale("/asr_realtime?mode=idle", "ja"), "/asr_realtime?mode=idle&lang=ja");
});

test("keeps all portal catalogs complete and falls back to English", () => {
  const englishKeys = Object.keys(messages.en);
  assert.deepEqual(Object.keys(messages), SUPPORTED_LOCALES);
  for (const locale of SUPPORTED_LOCALES) {
    assert.deepEqual(Object.keys(messages[locale]), englishKeys);
    assert.ok(Object.values(messages[locale]).every((value) => typeof value === "string" && value.length > 0));
  }
  assert.equal(translate("unknown", "hero.title"), messages.en["hero.title"]);
});

test("provides localized live status wording", () => {
  assert.equal(translate("en", "status.ready"), "Gateway and model capabilities are connected");
  assert.equal(translate("zh-TW", "status.ready"), "Gateway 與模型能力已連線");
  assert.equal(translate("ja", "status.ready"), "Gateway とモデル機能に接続しました");
  assert.equal(translate("ko", "status.ready"), "Gateway와 모델 기능이 연결되었습니다");
});

test("localizes the Agent listening hero message", () => {
  assert.equal(translate("en", "hero.title"), "Let your Agent listen freely,");
  assert.equal(translate("en", "hero.titleAccent"), "and join the conversation.");
  assert.equal(translate("zh-TW", "hero.title"), "讓你的 Agent 自由聆聽，");
  assert.equal(translate("zh-TW", "hero.titleAccent"), "自然接話。");
  assert.match(translate("ja", "hero.lede"), /Agent/);
  assert.match(translate("ko", "hero.lede"), /Agent/);
});

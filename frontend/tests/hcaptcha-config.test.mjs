import assert from "node:assert/strict";
import test from "node:test";

import { isHcaptchaEnabled } from "../app/lib/hcaptcha.ts";

test("CAPTCHA defaults to enabled when the environment variable is missing", () => {
  assert.equal(isHcaptchaEnabled(undefined), true);
});

test("CAPTCHA stays enabled for explicit true values", () => {
  assert.equal(isHcaptchaEnabled("true"), true);
  assert.equal(isHcaptchaEnabled("TRUE"), true);
  assert.equal(isHcaptchaEnabled(" true "), true);
});

test("CAPTCHA stays enabled for unrecognized values", () => {
  assert.equal(isHcaptchaEnabled(""), true);
  assert.equal(isHcaptchaEnabled("0"), true);
  assert.equal(isHcaptchaEnabled("no"), true);
});

test("CAPTCHA is disabled only for explicit false values", () => {
  assert.equal(isHcaptchaEnabled("false"), false);
  assert.equal(isHcaptchaEnabled("FALSE"), false);
  assert.equal(isHcaptchaEnabled(" false "), false);
});

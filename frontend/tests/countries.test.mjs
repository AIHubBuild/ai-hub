import test from "node:test";
import assert from "node:assert/strict";
import {
  COUNTRIES,
  countryNameFromCode,
  filterCountries,
  findCountry,
  normalizeCountryCode,
} from "../app/lib/countries.ts";

test("country catalog exposes ISO alpha-2 codes with full names", () => {
  assert.equal(COUNTRIES.length, 249);
  assert.equal(new Set(COUNTRIES.map((country) => country.code)).size, 249);
  assert.ok(COUNTRIES.every((country) => /^[A-Z]{2}$/.test(country.code)));
  assert.ok(
    COUNTRIES.every(
      (country) => country.name.length > 0 && country.name !== country.code,
    ),
  );
});

test("country names are displayed for stored ISO codes", () => {
  assert.equal(countryNameFromCode("DE"), "Germany");
  assert.equal(countryNameFromCode("NG"), "Nigeria");
  assert.equal(countryNameFromCode("US"), "United States");
  assert.equal(countryNameFromCode(" de "), "Germany");
  assert.equal(countryNameFromCode("xx"), "XX");
  assert.equal(countryNameFromCode(""), "");
});

test("country lookup resolves a stored code to its full name", () => {
  assert.equal(findCountry("DE")?.name, "Germany");
  assert.equal(findCountry("ng")?.name, "Nigeria");
  assert.equal(findCountry("not-a-code"), null);
});

test("country search matches names and codes", () => {
  assert.equal(filterCountries("germany")[0]?.code, "DE");
  assert.equal(filterCountries("ng")[0]?.code, "NG");
  assert.equal(filterCountries("cote")[0]?.code, "CI");
  assert.ok(filterCountries("united").some((country) => country.code === "GB"));
  assert.deepEqual(filterCountries("not-a-country"), []);
});

test("country code normalization keeps API-compatible two-letter codes", () => {
  assert.equal(normalizeCountryCode("de"), "DE");
  assert.equal(normalizeCountryCode(" NG "), "NG");
  assert.equal(normalizeCountryCode("USA"), null);
  assert.equal(normalizeCountryCode(""), null);
});

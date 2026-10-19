const COUNTRY_CODES = [
  "AF", "AL", "DZ", "AS", "AD", "AO", "AI", "AQ", "AG", "AR", "AM", "AW",
  "AU", "AT", "AZ", "BS", "BH", "BD", "BB", "BY", "BE", "BZ", "BJ", "BM",
  "BT", "BO", "BA", "BW", "BV", "BR", "IO", "BN", "BG", "BF", "BI", "KH",
  "CM", "CA", "CV", "KY", "CF", "TD", "CL", "CN", "CX", "CC", "CO", "KM",
  "CG", "CD", "CK", "CR", "CI", "HR", "CU", "CY", "CZ", "DK", "DJ", "DM",
  "DO", "EC", "EG", "SV", "GQ", "ER", "EE", "ET", "FK", "FO", "FJ", "FI",
  "FR", "GF", "PF", "TF", "GA", "GM", "GE", "DE", "GH", "GI", "GR", "GL",
  "GD", "GP", "GU", "GT", "GN", "GW", "GY", "HT", "HM", "VA", "HN", "HK",
  "HU", "IS", "IN", "ID", "IR", "IQ", "IE", "IL", "IT", "JM", "JP", "JO",
  "KZ", "KE", "KI", "KP", "KR", "KW", "KG", "LA", "LV", "LB", "LS", "LR",
  "LY", "LI", "LT", "LU", "MO", "MG", "MW", "MY", "MV", "ML", "MT", "MH",
  "MQ", "MR", "MU", "YT", "MX", "FM", "MD", "MC", "MN", "MS", "MA", "MZ",
  "MM", "NA", "NR", "NP", "NL", "NC", "NZ", "NI", "NE", "NG", "NU", "NF",
  "MP", "MK", "NO", "OM", "PK", "PW", "PS", "PA", "PG", "PY", "PE", "PH",
  "PN", "PL", "PT", "PR", "QA", "RE", "RO", "RU", "RW", "SH", "KN", "LC",
  "PM", "VC", "WS", "SM", "ST", "SA", "SN", "SC", "SL", "SG", "SK", "SI",
  "SB", "SO", "ZA", "GS", "ES", "LK", "SD", "SR", "SJ", "SZ", "SE", "CH",
  "SY", "TW", "TJ", "TZ", "TH", "TL", "TG", "TK", "TO", "TT", "TN", "TR",
  "TM", "TC", "TV", "UG", "UA", "AE", "GB", "US", "UM", "UY", "UZ", "VU",
  "VE", "VN", "VG", "VI", "WF", "EH", "YE", "ZM", "ZW", "AX", "BQ", "CW",
  "GG", "IM", "JE", "ME", "BL", "MF", "RS", "SX", "SS",
] as const;

export type CountryCode = (typeof COUNTRY_CODES)[number];

export interface Country {
  code: CountryCode;
  name: string;
}

const regionNames = (() => {
  try {
    return new Intl.DisplayNames(["en"], { type: "region" });
  } catch {
    return null;
  }
})();

function displayName(code: CountryCode): string {
  try {
    return regionNames?.of(code) ?? code;
  } catch {
    return code;
  }
}

const collator = new Intl.Collator("en");

export const COUNTRIES: readonly Country[] = COUNTRY_CODES.map((code) => ({
  code,
  name: displayName(code),
})).sort((left, right) => collator.compare(left.name, right.name));

const COUNTRY_BY_CODE = new Map<string, Country>(
  COUNTRIES.map((country) => [country.code, country]),
);

function normalizeSearch(value: string): string {
  return value
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase();
}

const COUNTRY_SEARCH = new Map(
  COUNTRIES.map((country) => [
    country.code,
    normalizeSearch(`${country.name} ${country.code}`),
  ]),
);

export function normalizeCountryCode(value: string | null | undefined): string | null {
  const trimmed = (value ?? "").trim().toUpperCase();
  if (!trimmed) {
    return null;
  }
  return /^[A-Z]{2}$/.test(trimmed) ? trimmed : null;
}

export function findCountry(value: string | null | undefined): Country | null {
  const code = normalizeCountryCode(value);
  return code === null ? null : (COUNTRY_BY_CODE.get(code) ?? null);
}

export function countryNameFromCode(value: string | null | undefined): string {
  const code = normalizeCountryCode(value);
  if (code === null) {
    return "";
  }
  return COUNTRY_BY_CODE.get(code)?.name ?? code;
}

export function filterCountries(query: string): readonly Country[] {
  const trimmed = query.trim();
  if (!trimmed) {
    return COUNTRIES;
  }

  const normalized = normalizeSearch(trimmed);
  const matches = COUNTRIES.filter((country) =>
    COUNTRY_SEARCH.get(country.code)?.includes(normalized),
  );
  const exactCode = trimmed.toUpperCase();
  const exact = matches.find((country) => country.code === exactCode);
  if (exact === undefined) {
    return matches;
  }
  return [exact, ...matches.filter((country) => country !== exact)];
}

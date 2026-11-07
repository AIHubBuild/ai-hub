export function isHcaptchaEnabled(
  value: string | undefined = process.env.NEXT_PUBLIC_HCAPTCHA_ENABLED,
): boolean {
  return (value ?? "true").trim().toLowerCase() !== "false";
}

export const HCAPTCHA_ENABLED = isHcaptchaEnabled();

"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { useAuth } from "../../components/auth/auth-provider";
import { Spinner } from "../../components/auth/spinner";
import { ApiError } from "../../lib/api";
import {
  fetchProfile,
  isValidPhone,
  normalizeCountryCode,
  saveProfile,
  type ProfileUpsertPayload,
} from "../../lib/profile";
import { getSupabase } from "../../lib/supabase";

type FieldErrors = {
  fullName?: string;
  phone?: string;
  country?: string;
  policies?: string;
};

export function CompleteRegistrationView() {
  const router = useRouter();
  const { session, loading: authLoading, configured } = useAuth();
  const [checking, setChecking] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});

  const [fullName, setFullName] = useState("");
  const [phone, setPhone] = useState("");
  const [country, setCountry] = useState("");
  const [city, setCity] = useState("");
  const [careerGoal, setCareerGoal] = useState("");
  const [marketingConsent, setMarketingConsent] = useState(false);
  const [acceptedPolicies, setAcceptedPolicies] = useState(false);
  const [policiesAcceptedAtSignup, setPoliciesAcceptedAtSignup] =
    useState(false);

  const userId = session?.user.id ?? null;
  const emailVerified = Boolean(session?.user.email_confirmed_at);

  useEffect(() => {
    let active = true;
    const check = async () => {
      await Promise.resolve();
      if (!active) {
        return;
      }
      if (!userId || !session || !emailVerified) {
        setChecking(false);
        return;
      }
      setChecking(true);
      setLoadError(null);
      try {
        const existing = await fetchProfile();
        if (!active) {
          return;
        }
        if (existing !== null) {
          router.replace("/profile");
          return;
        }
        const metadata = session.user.user_metadata ?? {};
        setFullName(
          typeof metadata.full_name === "string" ? metadata.full_name : "",
        );
        setPhone(typeof metadata.phone === "string" ? metadata.phone : "");
        setCountry(
          typeof metadata.country_code === "string"
            ? metadata.country_code
            : "",
        );
        setCity(typeof metadata.city === "string" ? metadata.city : "");
        setCareerGoal(
          typeof metadata.career_goal === "string" ? metadata.career_goal : "",
        );
        setMarketingConsent(metadata.marketing_consent === true);
        const accepted =
          metadata.terms_accepted === true &&
          metadata.privacy_accepted === true;
        setPoliciesAcceptedAtSignup(accepted);
        setAcceptedPolicies(accepted);
      } catch (caught) {
        if (!active) {
          return;
        }
        if (caught instanceof ApiError && caught.status === 403) {
          setLoadError(
            "Email verification is required before registration can be completed.",
          );
        } else {
          setLoadError("Your profile could not be checked. Try again.");
        }
      } finally {
        if (active) {
          setChecking(false);
        }
      }
    };
    void check();
    return () => {
      active = false;
    };
  }, [emailVerified, router, session, userId]);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setNotice(null);

    if (!emailVerified) {
      setError("Verify your email before completing registration.");
      return;
    }

    const errors: FieldErrors = {};
    if (fullName.trim().length < 2) {
      errors.fullName = "Enter your full name.";
    }
    if (!isValidPhone(phone)) {
      errors.phone = "Enter a valid phone number with 7 to 15 digits.";
    }
    const countryCode = normalizeCountryCode(country);
    if (country.trim() && countryCode === null) {
      errors.country = "Enter a two-letter country code, such as US.";
    }
    if (!policiesAcceptedAtSignup && !acceptedPolicies) {
      errors.policies = "Accept the Terms of Service and Privacy Notice.";
    }
    setFieldErrors(errors);
    if (Object.keys(errors).length > 0) {
      return;
    }

    const payload: ProfileUpsertPayload = {
      full_name: fullName.trim(),
      phone: phone.trim() || null,
      country_code: countryCode,
      city: city.trim() || null,
      career_goal: careerGoal.trim() || null,
      marketing_consent: marketingConsent,
      terms_accepted: policiesAcceptedAtSignup || acceptedPolicies,
      privacy_accepted: policiesAcceptedAtSignup || acceptedPolicies,
    };

    setSaving(true);
    try {
      const saved = await saveProfile(payload);
      if (saved === null) {
        setError("Your profile could not be saved.");
        return;
      }

      const client = getSupabase();
      if (client !== null) {
        const { error: metadataError } = await client.auth.updateUser({
          data: {
            full_name: payload.full_name,
            phone: payload.phone,
            country_code: payload.country_code,
            city: payload.city,
            career_goal: payload.career_goal,
            marketing_consent: payload.marketing_consent,
          },
        });
        if (metadataError) {
          setNotice(
            "Profile saved, but the account metadata could not be updated.",
          );
          return;
        }
      }

      router.push("/profile");
      router.refresh();
    } catch (caught) {
      if (caught instanceof ApiError && caught.status === 403) {
        setError(
          "Email verification is required before registration can be completed.",
        );
      } else {
        setError(
          caught instanceof ApiError
            ? caught.message
            : "Your profile could not be saved.",
        );
      }
    } finally {
      setSaving(false);
    }
  }

  if (authLoading) {
    return (
      <div className="flex items-center justify-center py-12 text-sm text-muted">
        <Spinner className="mr-2" />
        Checking your account…
      </div>
    );
  }

  if (!configured || session === null) {
    return (
      <div className="py-4 text-center">
        <p className="ui-eyebrow">Registration</p>
        <h1 className="mt-3 text-[26px] font-semibold tracking-[-0.03em] text-ink">
          Sign in to complete registration
        </h1>
        <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-muted">
          Verify your email first, then sign in to finish your profile.
        </p>
        <Link
          href="/login?redirect=%2Fregister%2Fcomplete"
          className="ui-button ui-button-primary mt-6 h-11 w-full"
        >
          Sign in
        </Link>
      </div>
    );
  }

  if (!emailVerified) {
    return (
      <div className="py-4 text-center">
        <p className="ui-eyebrow">Verification required</p>
        <h1 className="mt-3 text-[26px] font-semibold tracking-[-0.03em] text-ink">
          Confirm your email first
        </h1>
        <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-muted">
          Profile completion is unavailable until your email address is
          verified.
        </p>
        <Link href="/login" className="ui-button ui-button-primary mt-6 h-11 w-full">
          Return to sign in
        </Link>
      </div>
    );
  }

  return (
    <div>
      <header className="text-center">
        <p className="ui-eyebrow">Registration</p>
        <h1 className="mt-3 text-[28px] font-semibold tracking-[-0.035em] text-ink">
          Complete your profile
        </h1>
        <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-muted">
          Your email is verified. Add your location and optional details to
          finish setting up your private workspace.
        </p>
      </header>

      {checking ? (
        <div className="flex items-center justify-center py-10 text-sm text-muted">
          <Spinner className="mr-2" />
          Checking your profile…
        </div>
      ) : loadError ? (
        <div className="auth-message-error mt-6 rounded-xl border p-4 text-sm">
          <p>{loadError}</p>
          <Link href="/login" className="ui-button ui-button-secondary mt-3">
            Return to sign in
          </Link>
        </div>
      ) : (
        <form onSubmit={handleSubmit} className="mt-6 space-y-4">
          <div>
            <label
              htmlFor="registration-full-name"
              className="mb-1.5 block text-xs font-semibold uppercase tracking-[0.12em] text-ink-soft"
            >
              Full name
            </label>
            <input
              id="registration-full-name"
              type="text"
              required
              minLength={2}
              maxLength={200}
              autoComplete="name"
              value={fullName}
              onChange={(event) => setFullName(event.target.value)}
              aria-invalid={fieldErrors.fullName ? true : undefined}
              aria-describedby={
                fieldErrors.fullName ? "registration-name-error" : undefined
              }
              className="ui-field"
            />
            {fieldErrors.fullName && (
              <p id="registration-name-error" className="auth-field-error mt-1.5 text-xs">
                {fieldErrors.fullName}
              </p>
            )}
          </div>

          <div className="grid gap-3 sm:grid-cols-2">
            <div>
              <label
                htmlFor="registration-country"
                className="mb-1.5 block text-xs font-semibold uppercase tracking-[0.12em] text-ink-soft"
              >
                Country <span className="font-normal normal-case tracking-normal text-muted">(optional)</span>
              </label>
              <input
                id="registration-country"
                type="text"
                maxLength={2}
                pattern="[A-Za-z]{2}"
                placeholder="US"
                value={country}
                onChange={(event) => setCountry(event.target.value)}
                aria-invalid={fieldErrors.country ? true : undefined}
                aria-describedby={
                  fieldErrors.country ? "registration-country-error" : undefined
                }
                className="ui-field uppercase"
              />
              {fieldErrors.country && (
                <p id="registration-country-error" className="auth-field-error mt-1.5 text-xs">
                  {fieldErrors.country}
                </p>
              )}
            </div>
            <div>
              <label
                htmlFor="registration-city"
                className="mb-1.5 block text-xs font-semibold uppercase tracking-[0.12em] text-ink-soft"
              >
                City <span className="font-normal normal-case tracking-normal text-muted">(optional)</span>
              </label>
              <input
                id="registration-city"
                type="text"
                maxLength={100}
                autoComplete="address-level2"
                value={city}
                onChange={(event) => setCity(event.target.value)}
                className="ui-field"
              />
            </div>
          </div>

          <div className="grid gap-3 sm:grid-cols-2">
            <div>
              <label
                htmlFor="registration-phone"
                className="mb-1.5 block text-xs font-semibold uppercase tracking-[0.12em] text-ink-soft"
              >
                Phone <span className="font-normal normal-case tracking-normal text-muted">(optional)</span>
              </label>
              <input
                id="registration-phone"
                type="tel"
                maxLength={32}
                autoComplete="tel"
                value={phone}
                onChange={(event) => setPhone(event.target.value)}
                aria-invalid={fieldErrors.phone ? true : undefined}
                aria-describedby={
                  fieldErrors.phone ? "registration-phone-error" : undefined
                }
                className="ui-field"
              />
              {fieldErrors.phone && (
                <p id="registration-phone-error" className="auth-field-error mt-1.5 text-xs">
                  {fieldErrors.phone}
                </p>
              )}
            </div>
            <div>
              <label
                htmlFor="registration-career-goal"
                className="mb-1.5 block text-xs font-semibold uppercase tracking-[0.12em] text-ink-soft"
              >
                Career goal <span className="font-normal normal-case tracking-normal text-muted">(optional)</span>
              </label>
              <input
                id="registration-career-goal"
                type="text"
                maxLength={200}
                value={careerGoal}
                onChange={(event) => setCareerGoal(event.target.value)}
                className="ui-field"
              />
            </div>
          </div>

          <label className="flex items-start gap-2.5 text-xs leading-5 text-ink-soft">
            <input
              type="checkbox"
              checked={marketingConsent}
              onChange={(event) => setMarketingConsent(event.target.checked)}
              className="mt-0.5 h-4 w-4 rounded border-line"
            />
            <span>
              Send me optional product news and marketing emails. Separate
              from account messages.
            </span>
          </label>

          {policiesAcceptedAtSignup ? (
            <p className="rounded-xl border border-success/20 bg-success/5 px-3 py-2 text-xs leading-5 text-ink-soft">
              Terms of Service and Privacy Notice accepted when you created
              your account.{" "}
              <Link href="/terms" className="text-accent underline underline-offset-2">
                Terms
              </Link>{" "}
              ·{" "}
              <Link href="/privacy" className="text-accent underline underline-offset-2">
                Privacy
              </Link>
            </p>
          ) : (
            <div>
              <label className="flex items-start gap-2.5 text-xs leading-5 text-ink-soft">
                <input
                  type="checkbox"
                  required
                  checked={acceptedPolicies}
                  onChange={(event) => setAcceptedPolicies(event.target.checked)}
                  aria-invalid={fieldErrors.policies ? true : undefined}
                  aria-describedby={
                    fieldErrors.policies ? "registration-policies-error" : undefined
                  }
                  className="mt-0.5 h-4 w-4 rounded border-line"
                />
                <span>
                  I accept the{" "}
                  <Link href="/terms" target="_blank" rel="noreferrer" className="font-medium text-accent underline underline-offset-2">
                    Terms of Service
                  </Link>{" "}
                  and{" "}
                  <Link href="/privacy" target="_blank" rel="noreferrer" className="font-medium text-accent underline underline-offset-2">
                    Privacy Notice
                  </Link>
                  .
                </span>
              </label>
              {fieldErrors.policies && (
                <p id="registration-policies-error" className="auth-field-error mt-1.5 text-xs">
                  {fieldErrors.policies}
                </p>
              )}
            </div>
          )}

          {error && (
            <p role="alert" className="auth-message-error rounded-xl border px-3 py-2 text-sm">
              {error}
            </p>
          )}
          {notice && (
            <p className="auth-message-success rounded-xl border px-3 py-2 text-sm">
              {notice}
            </p>
          )}

          <button
            type="submit"
            disabled={saving}
            className="ui-button ui-button-primary h-11 w-full"
          >
            {saving && <Spinner />}
            {saving ? "Saving…" : "Complete registration"}
          </button>
        </form>
      )}
    </div>
  );
}

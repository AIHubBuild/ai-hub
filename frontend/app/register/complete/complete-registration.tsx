"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { useAuth } from "../../components/auth/auth-provider";
import { ApiError } from "../../lib/api";
import {
  fetchProfile,
  isValidPhone,
  normalizeCountryCode,
  saveProfile,
  type ProfileUpsertPayload,
} from "../../lib/profile";
import { getSupabase } from "../../lib/supabase";

export function CompleteRegistrationView() {
  const router = useRouter();
  const { session, loading: authLoading, configured } = useAuth();
  const [checking, setChecking] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const [fullName, setFullName] = useState("");
  const [phone, setPhone] = useState("");
  const [country, setCountry] = useState("");
  const [city, setCity] = useState("");
  const [careerGoal, setCareerGoal] = useState("");
  const [marketingConsent, setMarketingConsent] = useState(false);
  const [acceptedPolicies, setAcceptedPolicies] = useState(false);

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
      } catch (caught) {
        if (!active) {
          return;
        }
        if (caught instanceof ApiError && caught.status === 403) {
          setLoadError("Email verification is required before registration can be completed.");
        } else if (caught instanceof ApiError && caught.status === 404) {
          // No profile yet; the form can proceed.
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
    const trimmedName = fullName.trim();
    if (trimmedName.length < 2) {
      setError("Enter your full name.");
      return;
    }
    if (!isValidPhone(phone)) {
      setError("Enter a valid phone number with 7 to 15 digits.");
      return;
    }
    const countryCode = normalizeCountryCode(country);
    if (country.trim() && countryCode === null) {
      setError("Enter a two-letter country code, such as US.");
      return;
    }
    if (!acceptedPolicies) {
      setError(
        "Accept the Terms of Service and Privacy Notice to complete registration.",
      );
      return;
    }

    const payload: ProfileUpsertPayload = {
      full_name: trimmedName,
      phone: phone.trim() || null,
      country_code: countryCode,
      city: city.trim() || null,
      career_goal: careerGoal.trim() || null,
      marketing_consent: marketingConsent,
      terms_accepted: true,
      privacy_accepted: true,
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
        setError("Email verification is required before registration can be completed.");
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
      <main className="mx-auto w-full max-w-2xl flex-1 px-4 py-12 sm:px-6">
        <p className="text-sm text-muted">Checking your account…</p>
      </main>
    );
  }

  if (!configured || session === null) {
    return (
      <main className="mx-auto w-full max-w-2xl flex-1 px-4 py-12 sm:px-6">
        <section className="rounded-2xl bg-surface p-8 text-center ring-1 ring-line/80">
          <p className="ui-eyebrow">Registration</p>
          <h1 className="ui-display mt-3 text-3xl text-ink">
            Sign in to complete registration
          </h1>
          <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-muted">
            Verify your email first, then sign in to finish your profile.
          </p>
          <Link
            href="/login?redirect=%2Fregister%2Fcomplete"
            className="ui-button ui-button-primary mt-5"
          >
            Sign in
          </Link>
        </section>
      </main>
    );
  }

  if (!emailVerified) {
    return (
      <main className="mx-auto w-full max-w-2xl flex-1 px-4 py-12 sm:px-6">
        <section className="rounded-2xl bg-surface p-8 text-center ring-1 ring-line/80">
          <p className="ui-eyebrow">Verification required</p>
          <h1 className="ui-display mt-3 text-3xl text-ink">
            Confirm your email first
          </h1>
          <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-muted">
            Profile completion is unavailable until your email address is
            verified.
          </p>
          <Link
            href="/login"
            className="ui-button ui-button-primary mt-5"
          >
            Return to sign in
          </Link>
        </section>
      </main>
    );
  }

  return (
    <main className="mx-auto w-full max-w-2xl flex-1 px-4 py-10 sm:px-6 sm:py-12">
      <header className="border-b border-line pb-6">
        <p className="ui-eyebrow">Registration</p>
        <h1 className="ui-display mt-3 text-3xl text-ink">
          Complete your profile
        </h1>
        <p className="mt-3 text-sm leading-6 text-muted">
          Your email is verified. Add the details that help personalize your
          experience. Home address is not required.
        </p>
      </header>

      {checking ? (
        <p className="mt-6 text-sm text-muted">Checking your profile…</p>
      ) : loadError ? (
        <div className="mt-6 rounded-xl border-l-2 border-danger bg-surface p-4 text-sm text-ink-soft">
          <p>{loadError}</p>
          <Link href="/login" className="ui-button ui-button-secondary mt-3">
            Return to sign in
          </Link>
        </div>
      ) : (
        <form
          onSubmit={handleSubmit}
          className="mt-6 rounded-2xl bg-surface p-6 ring-1 ring-line/80"
        >
          <label
            htmlFor="registration-full-name"
            className="mb-1.5 block text-sm font-medium text-ink"
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
            className="ui-field"
          />

          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            <div>
              <label
                htmlFor="registration-phone"
                className="mb-1.5 block text-sm font-medium text-ink"
              >
                Phone{" "}
                <span className="font-normal text-muted">(optional)</span>
              </label>
              <input
                id="registration-phone"
                type="tel"
                maxLength={32}
                autoComplete="tel"
                value={phone}
                onChange={(event) => setPhone(event.target.value)}
                className="ui-field"
              />
            </div>
            <div>
              <label
                htmlFor="registration-country"
                className="mb-1.5 block text-sm font-medium text-ink"
              >
                Country{" "}
                <span className="font-normal text-muted">(optional)</span>
              </label>
              <input
                id="registration-country"
                type="text"
                maxLength={2}
                pattern="[A-Za-z]{2}"
                placeholder="US"
                value={country}
                onChange={(event) => setCountry(event.target.value)}
                className="ui-field uppercase"
              />
            </div>
          </div>

          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            <div>
              <label
                htmlFor="registration-city"
                className="mb-1.5 block text-sm font-medium text-ink"
              >
                City <span className="font-normal text-muted">(optional)</span>
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
            <div>
              <label
                htmlFor="registration-career-goal"
                className="mb-1.5 block text-sm font-medium text-ink"
              >
                Career goal{" "}
                <span className="font-normal text-muted">(optional)</span>
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

          <label className="mt-4 flex items-start gap-2.5 text-sm text-ink-soft">
            <input
              type="checkbox"
              checked={marketingConsent}
              onChange={(event) => setMarketingConsent(event.target.checked)}
              className="mt-0.5 h-4 w-4 rounded border-line"
            />
            <span>
              Send me optional product news and marketing emails. This is
              separate from account messages and can be changed later.
            </span>
          </label>

          <label className="mt-3 flex items-start gap-2.5 text-sm text-ink-soft">
            <input
              type="checkbox"
              required
              checked={acceptedPolicies}
              onChange={(event) => setAcceptedPolicies(event.target.checked)}
              className="mt-0.5 h-4 w-4 rounded border-line"
            />
            <span>
              I accept the{" "}
              <Link
                href="/terms"
                target="_blank"
                rel="noreferrer"
                className="font-medium text-accent underline underline-offset-2"
              >
                Terms of Service
              </Link>{" "}
              and{" "}
              <Link
                href="/privacy"
                target="_blank"
                rel="noreferrer"
                className="font-medium text-accent underline underline-offset-2"
              >
                Privacy Notice
              </Link>
              .
            </span>
          </label>

          {error !== null && (
            <p
              role="alert"
              className="mt-4 border-l-2 border-danger bg-surface-muted px-3 py-2 text-sm text-ink-soft"
            >
              {error}
            </p>
          )}
          {notice !== null && (
            <p className="mt-4 border-l-2 border-success bg-surface-muted px-3 py-2 text-sm text-ink-soft">
              {notice}
            </p>
          )}

          <button
            type="submit"
            disabled={saving}
            className="ui-button ui-button-primary mt-5"
          >
            {saving ? "Saving…" : "Complete registration"}
          </button>
        </form>
      )}
    </main>
  );
}

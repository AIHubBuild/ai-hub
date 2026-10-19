"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useAuth } from "../components/auth/auth-provider";
import { ApiError } from "../lib/api";
import {
  fetchProfile,
  isValidPhone,
  normalizeCountryCode,
  saveProfile,
  type ProfileUpsertPayload,
  type UserProfileData,
} from "../lib/profile";
import { getSupabase } from "../lib/supabase";

function policyDate(value: string): string {
  return new Date(value).toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

export function ProfileView() {
  const { session, loading: authLoading, configured } = useAuth();
  const [profile, setProfile] = useState<UserProfileData | null>(null);
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const [fullName, setFullName] = useState("");
  const [phone, setPhone] = useState("");
  const [country, setCountry] = useState("");
  const [city, setCity] = useState("");
  const [careerGoal, setCareerGoal] = useState("");
  const [marketingConsent, setMarketingConsent] = useState(false);
  const [acceptedPolicies, setAcceptedPolicies] = useState(false);

  const userId = session?.user.id ?? null;

  useEffect(() => {
    if (!userId || !session) {
      return;
    }
    let active = true;
    const load = async () => {
      await Promise.resolve();
      if (!active) {
        return;
      }
      setLoading(true);
      setLoadError(null);
      try {
        const next = await fetchProfile();
        if (!active) {
          return;
        }
        setProfile(next);
        if (next !== null) {
          setFullName(next.full_name);
          setPhone(next.phone ?? "");
          setCountry(next.country_code ?? "");
          setCity(next.city ?? "");
          setCareerGoal(next.career_goal ?? "");
          setMarketingConsent(next.marketing_consent);
          setAcceptedPolicies(true);
        } else {
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
          setAcceptedPolicies(
            metadata.terms_accepted === true &&
              metadata.privacy_accepted === true,
          );
        }
      } catch (caught) {
        if (active) {
          setLoadError(
            caught instanceof ApiError
              ? caught.message
              : "Your profile could not be loaded.",
          );
        }
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    };
    void load();
    return () => {
      active = false;
    };
  }, [userId, session]);

  async function handleSave(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setNotice(null);

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
    if (profile === null && !acceptedPolicies) {
      setError(
        "Accept the Terms of Service and Privacy Notice to complete your profile.",
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
      terms_accepted: profile === null ? acceptedPolicies : true,
      privacy_accepted: profile === null ? acceptedPolicies : true,
    };

    setSaving(true);
    try {
      const saved = await saveProfile(payload);
      if (saved !== null) {
        setProfile(saved);
        setFullName(saved.full_name);
        setPhone(saved.phone ?? "");
        setCountry(saved.country_code ?? "");
        setCity(saved.city ?? "");
        setCareerGoal(saved.career_goal ?? "");
        setMarketingConsent(saved.marketing_consent);
        setAcceptedPolicies(true);
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
      setNotice("Profile saved.");
    } catch (caught) {
      setError(
        caught instanceof ApiError
          ? caught.message
          : "Your profile could not be saved.",
      );
    } finally {
      setSaving(false);
    }
  }

  if (authLoading) {
    return (
      <main className="mx-auto w-full max-w-2xl flex-1 px-4 py-12 sm:px-6">
        <p className="text-sm text-muted">Loading account…</p>
      </main>
    );
  }

  if (!configured || session === null) {
    return (
      <main className="mx-auto w-full max-w-2xl flex-1 px-4 py-12 sm:px-6">
        <section className="rounded-2xl bg-surface p-8 text-center ring-1 ring-line/80">
          <p className="ui-eyebrow">Account</p>
          <h1 className="ui-display mt-3 text-3xl text-ink">
            Sign in to manage your profile
          </h1>
          <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-muted">
            Your profile is private to your account.
          </p>
          <Link
            href="/login?redirect=%2Fprofile"
            className="ui-button ui-button-primary mt-5"
          >
            Sign in
          </Link>
        </section>
      </main>
    );
  }

  const email = profile?.email ?? session.user.email ?? null;
  const emailVerified = Boolean(session.user.email_confirmed_at);

  return (
    <main className="mx-auto w-full max-w-2xl flex-1 px-4 py-10 sm:px-6 sm:py-12">
      <header className="border-b border-line pb-6">
        <p className="ui-eyebrow">Account profile</p>
        <h1 className="ui-display mt-3 text-3xl text-ink">Your profile</h1>
        <p className="mt-3 text-sm leading-6 text-muted">
          This information is stored separately from your login credentials.
          Passwords are never stored in the profile.
        </p>
      </header>

      {loading ? (
        <p className="mt-6 text-sm text-muted">Loading profile…</p>
      ) : loadError ? (
        <div className="mt-6 rounded-xl border-l-2 border-danger bg-surface p-4 text-sm text-ink-soft">
          <p>{loadError}</p>
          <button
            type="button"
            onClick={() => window.location.reload()}
            className="ui-button ui-button-secondary mt-3"
          >
            Retry
          </button>
        </div>
      ) : (
        <div className="mt-6 space-y-5">
          <section className="rounded-2xl bg-surface p-6 ring-1 ring-line/80">
            <h2 className="text-sm font-semibold text-ink">Account email</h2>
            <p className="mt-2 break-all text-sm text-ink-soft">
              {email ?? "No email available"}
            </p>
            <p
              className={`mt-2 text-xs font-medium ${
                emailVerified ? "text-success" : "text-danger"
              }`}
            >
              {emailVerified
                ? "Email verified"
                : "Email verification pending"}
            </p>
          </section>

          <form
            onSubmit={handleSave}
            className="rounded-2xl bg-surface p-6 ring-1 ring-line/80"
          >
            <h2 className="text-sm font-semibold text-ink">
              {profile === null ? "Complete your profile" : "Profile details"}
            </h2>

            <label
              htmlFor="profile-full-name"
              className="mb-1.5 mt-4 block text-sm font-medium text-ink"
            >
              Full name
            </label>
            <input
              id="profile-full-name"
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
                  htmlFor="profile-phone"
                  className="mb-1.5 block text-sm font-medium text-ink"
                >
                  Phone{" "}
                  <span className="font-normal text-muted">(optional)</span>
                </label>
                <input
                  id="profile-phone"
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
                  htmlFor="profile-country"
                  className="mb-1.5 block text-sm font-medium text-ink"
                >
                  Country{" "}
                  <span className="font-normal text-muted">(optional)</span>
                </label>
                <input
                  id="profile-country"
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
                  htmlFor="profile-city"
                  className="mb-1.5 block text-sm font-medium text-ink"
                >
                  City{" "}
                  <span className="font-normal text-muted">(optional)</span>
                </label>
                <input
                  id="profile-city"
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
                  htmlFor="profile-career-goal"
                  className="mb-1.5 block text-sm font-medium text-ink"
                >
                  Career goal{" "}
                  <span className="font-normal text-muted">(optional)</span>
                </label>
                <input
                  id="profile-career-goal"
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
                onChange={(event) =>
                  setMarketingConsent(event.target.checked)
                }
                className="mt-0.5 h-4 w-4 rounded border-line"
              />
              <span>
                Send me optional product news and marketing emails. This is
                separate from account messages.
              </span>
            </label>

            {profile === null ? (
              <label className="mt-3 flex items-start gap-2.5 text-sm text-ink-soft">
                <input
                  type="checkbox"
                  required
                  checked={acceptedPolicies}
                  onChange={(event) =>
                    setAcceptedPolicies(event.target.checked)
                  }
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
            ) : (
              <p className="mt-3 text-xs leading-5 text-muted">
                Terms accepted {policyDate(profile.terms_accepted_at)} (version{" "}
                {profile.terms_version}); Privacy Notice accepted{" "}
                {policyDate(profile.privacy_accepted_at)} (version{" "}
                {profile.privacy_version}).
              </p>
            )}

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
              {saving ? "Saving…" : "Save profile"}
            </button>
          </form>
        </div>
      )}
    </main>
  );
}

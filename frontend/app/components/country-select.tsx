"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import {
  countryNameFromCode,
  filterCountries,
  normalizeCountryCode,
  type Country,
} from "../lib/countries";

interface CountrySelectProps {
  id: string;
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  ariaInvalid?: boolean;
  ariaDescribedBy?: string;
}

export function CountrySelect({
  id,
  value,
  onChange,
  placeholder = "Search countries",
  ariaInvalid,
  ariaDescribedBy,
}: CountrySelectProps) {
  const listboxId = `${id}-listbox`;
  const selectedName = countryNameFromCode(value);
  const selectedCode = normalizeCountryCode(value);
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [activeIndex, setActiveIndex] = useState(0);
  const rootRef = useRef<HTMLDivElement>(null);

  const filtered = useMemo(
    () => filterCountries(open ? query : ""),
    [open, query],
  );
  const activeCountry = filtered[activeIndex];

  function optionId(code: string): string {
    return `${id}-option-${code}`;
  }

  function openList(nextQuery = "") {
    const results = filterCountries(nextQuery);
    const selectedIndex = selectedCode
      ? results.findIndex((country) => country.code === selectedCode)
      : 0;
    setOpen(true);
    setQuery(nextQuery);
    setActiveIndex(selectedIndex >= 0 ? selectedIndex : 0);
  }

  function closeList() {
    setOpen(false);
    setQuery("");
    setActiveIndex(0);
  }

  function selectCountry(country: Country) {
    onChange(country.code);
    setOpen(false);
    setQuery("");
    setActiveIndex(0);
  }

  function clearSelection() {
    onChange("");
    setOpen(false);
    setQuery("");
    setActiveIndex(0);
  }

  function handleKeyDown(event: React.KeyboardEvent<HTMLInputElement>) {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      if (!open) {
        openList("");
        return;
      }
      setActiveIndex((index) =>
        Math.min(index + 1, Math.max(filtered.length - 1, 0)),
      );
      return;
    }

    if (event.key === "ArrowUp") {
      event.preventDefault();
      if (!open) {
        const results = filterCountries("");
        setOpen(true);
        setQuery("");
        setActiveIndex(Math.max(results.length - 1, 0));
        return;
      }
      setActiveIndex((index) => Math.max(index - 1, 0));
      return;
    }

    if (event.key === "Home" && open) {
      event.preventDefault();
      setActiveIndex(0);
      return;
    }

    if (event.key === "End" && open) {
      event.preventDefault();
      setActiveIndex(Math.max(filtered.length - 1, 0));
      return;
    }

    if (event.key === "Enter" && open) {
      event.preventDefault();
      if (activeCountry !== undefined) {
        selectCountry(activeCountry);
      }
      return;
    }

    if (event.key === "Escape" && open) {
      event.preventDefault();
      closeList();
      return;
    }

    if (event.key === "Tab" && open) {
      closeList();
    }
  }

  useEffect(() => {
    if (!open) {
      return;
    }
    const onPointerDown = (event: PointerEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) {
        setOpen(false);
        setQuery("");
        setActiveIndex(0);
      }
    };
    document.addEventListener("pointerdown", onPointerDown);
    return () => document.removeEventListener("pointerdown", onPointerDown);
  }, [open]);

  useEffect(() => {
    if (!open || activeCountry === undefined) {
      return;
    }
    document
      .getElementById(`${id}-option-${activeCountry.code}`)
      ?.scrollIntoView({ block: "nearest" });
  }, [activeCountry, id, open]);

  return (
    <div ref={rootRef} className="relative">
      <input
        id={id}
        type="text"
        role="combobox"
        aria-expanded={open}
        aria-controls={listboxId}
        aria-haspopup="listbox"
        aria-autocomplete="list"
        aria-activedescendant={
          open && activeCountry !== undefined
            ? optionId(activeCountry.code)
            : undefined
        }
        aria-invalid={ariaInvalid ? true : undefined}
        aria-describedby={ariaDescribedBy}
        autoComplete="off"
        autoCorrect="off"
        spellCheck={false}
        inputMode="search"
        placeholder={placeholder}
        value={open ? query : selectedName}
        onChange={(event) => {
          setOpen(true);
          setQuery(event.target.value);
          setActiveIndex(0);
        }}
        onFocus={() => {
          if (!open) {
            openList("");
          }
        }}
        onKeyDown={handleKeyDown}
        className="ui-field pr-10"
      />
      {selectedName && (
        <button
          type="button"
          aria-label="Clear country selection"
          onMouseDown={(event) => event.preventDefault()}
          onClick={clearSelection}
          className="absolute inset-y-0 right-0 flex w-9 items-center justify-center text-muted transition-colors hover:text-ink focus-visible:text-ink focus-visible:outline-none"
        >
          <svg
            aria-hidden="true"
            viewBox="0 0 16 16"
            className="h-3.5 w-3.5"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.75"
            strokeLinecap="round"
          >
            <path d="M4 4l8 8M12 4l-8 8" />
          </svg>
        </button>
      )}
      {open && (
        <div className="absolute z-30 mt-1 w-full overflow-hidden rounded-xl border border-line bg-surface shadow-xl">
          {filtered.length === 0 ? (
            <p
              role="status"
              className="px-3 py-2.5 text-sm text-muted"
            >
              No countries found.
            </p>
          ) : (
            <ul
              id={listboxId}
              role="listbox"
              aria-label="Countries"
              className="max-h-60 touch-manipulation overflow-y-auto overscroll-contain py-1"
            >
              {filtered.map((country, index) => {
                const isActive = index === activeIndex;
                const isSelected = country.code === selectedCode;
                return (
                  <li
                    key={country.code}
                    id={optionId(country.code)}
                    role="option"
                    aria-selected={isSelected}
                    onMouseDown={(event) => event.preventDefault()}
                    onClick={() => selectCountry(country)}
                    onMouseEnter={() => setActiveIndex(index)}
                    className={`flex cursor-pointer items-center justify-between gap-3 px-3 py-2 text-sm ${
                      isActive
                        ? "bg-line/60 text-ink"
                        : "text-ink-soft hover:bg-line/40"
                    } ${isSelected ? "font-semibold" : ""}`}
                  >
                    <span>{country.name}</span>
                    <span className="text-xs font-normal tracking-wide text-muted">
                      {country.code}
                    </span>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}

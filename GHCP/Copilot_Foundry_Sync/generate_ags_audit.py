#!/usr/bin/env python3
"""
Full Audit Pack (Option 4) — Portable script.

Usage:
    python generate_ags_audit.py
    python generate_ags_audit.py --input gh_login_output.csv --outdir ./outputs
"""

import csv
import argparse
import platform
import os
from pathlib import Path
from datetime import datetime
import re
from collections import defaultdict, Counter

# -------------------------
# Configuration / Defaults
# -------------------------
DEFAULT_INPUT = "gh_login_output.csv"
OUT_AGS_MEMBERS = "ags_members.txt"
OUT_NO_LOGIN = "no_gh_login_found_from_ags.txt"
OUT_AUDIT_LOG = "ags_processing_audit_log.txt"

# treat these (after strip+lower) as blank
BLANK_VALUES = {"", " ", "null", "none", "n/a"}

# max sample lines to show for each category in the audit
SAMPLE_LIMIT = 20

EMAIL_REGEX = re.compile(r"^[^@ \t\r\n]+@[^@ \t\r\n]+\.[^@ \t\r\n]+$")  # simple email sanity check


# -------------------------
# Helpers
# -------------------------
def is_email_valid(email: str) -> bool:
    return bool(EMAIL_REGEX.match(email))


def detect_suspicious_login(val: str) -> bool:
    """
    Heuristics to detect suspicious login values:
      - contains '@' (looks like an email)
      - contains spaces
      - length is zero (should be handled earlier)
      - contains characters unlikely for GH login (we'll just flag emails and spaces)
    """
    if "@" in val:
        return True
    if " " in val:
        return True
    return False


def write_list_to_file(path: Path, items):
    with path.open("w", encoding="utf-8", newline="") as f:
        for it in items:
            f.write(f"{it}\n")


# -------------------------
# Main processing
# -------------------------
def process_file(input_path: Path, out_dir: Path):
    # prepare outputs dir
    out_dir.mkdir(parents=True, exist_ok=True)

    # Output file paths
    members_path = out_dir / OUT_AGS_MEMBERS
    no_login_path = out_dir / OUT_NO_LOGIN
    audit_log_path = out_dir / OUT_AUDIT_LOG

    # Counters and collectors
    total_rows = 0
    emails_no_login_set = set()
    logins_with_value_set = set()

    # Duplicates tracking (lists to include samples)
    duplicate_emails = Counter()
    duplicate_logins = Counter()

    # Data quality trackers
    malformed_emails_samples = []
    suspicious_logins_samples = []
    blank_breakdown = Counter()  # counts per cleaned blank token encountered (cleaned)
    blank_examples = defaultdict(list)  # store up to SAMPLE_LIMIT examples per blank token

    # Additional counters
    rows_missing_email = 0
    rows_missing_login_field = 0

    # For audit summary: track how many rows added (unique) vs duplicates skipped
    added_emails_count = 0
    added_logins_count = 0

    # Open and read CSV
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    # Attempt to open CSV (utf-8). If fails, user can re-run with appropriate encoding.
    with input_path.open("r", encoding="utf-8", newline="") as infile:
        reader = csv.DictReader(infile)
        # Determine if GitHub Login or Email columns present
        headers = reader.fieldnames or []
        has_login_col = any(h.lower() in ("github login", "github_login", "githublogin", "gh login", "gh_login", "login") for h in headers)
        if not has_login_col:
            # still proceed; we will use "GitHub Login" key if present, else fall back to None.
            rows_missing_login_field = 0  # will increment per row if key missing

        # Normalize header key access: prefer "GitHub Login" as provided originally,
        # but fallback to best match if different.
        def get_col_value(row, column_names):
            for c in column_names:
                if c in row:
                    return row[c]
            return ""

        # Build likely names for email and login
        possible_email_keys = [k for k in headers if k and k.lower() in ("email", "e-mail", "email address", "email_address")]
        possible_login_keys = [k for k in headers if k and k.lower() in ("github login", "github_login", "githublogin", "gh login", "gh_login", "login", "username", "user")]

        # fallback keys if none found
        if not possible_email_keys:
            possible_email_keys = ["Email"]
        if not possible_login_keys:
            possible_login_keys = ["GitHub Login"]

        for row_idx, row in enumerate(reader, start=1):
            total_rows += 1

            # Extract email and login using heuristics above
            raw_email = get_col_value(row, possible_email_keys)
            raw_login = get_col_value(row, possible_login_keys)

            # Normalize/trimming
            email = (raw_email or "").strip()
            raw_login_original = raw_login if raw_login is not None else ""
            login_trimmed = raw_login_original.strip()

            # For blank detection only: use lowercased stripped version
            login_for_blank_check = str(raw_login_original).strip().lower()

            # Blank breakdown
            if login_for_blank_check in BLANK_VALUES:
                blank_breakdown[login_for_blank_check] += 1
                if len(blank_examples[login_for_blank_check]) < SAMPLE_LIMIT:
                    blank_examples[login_for_blank_check].append((row_idx, raw_login_original))

            # Basic checks and collection
            if login_for_blank_check in BLANK_VALUES:
                # This row considered "no github login"
                if not email:
                    rows_missing_email += 1
                else:
                    if email not in emails_no_login_set:
                        emails_no_login_set.add(email)
                        added_emails_count += 1
                    else:
                        duplicate_emails[email] += 1
            else:
                # Row has a GH login value
                login_to_store = login_trimmed  # preserve original case except trimming whitespace
                # detect suspicious values (email-like or containing spaces)
                if detect_suspicious_login(login_to_store):
                    if len(suspicious_logins_samples) < SAMPLE_LIMIT:
                        suspicious_logins_samples.append((row_idx, login_to_store, email))

                # Add to set or count duplicate if already present
                if login_to_store not in logins_with_value_set:
                    logins_with_value_set.add(login_to_store)
                    added_logins_count += 1
                else:
                    duplicate_logins[login_to_store] += 1

                # If login looks like an email, also log it in malformed samples
                if "@" in login_to_store:
                    if len(malformed_emails_samples) < SAMPLE_LIMIT:
                        malformed_emails_samples.append((row_idx, login_to_store, email))

    # Prepare outputs
    # Sort outputs for deterministic order (case-insensitive sort but keep original case)
    members_sorted = sorted(logins_with_value_set, key=lambda s: s.lower())
    no_login_sorted = sorted(emails_no_login_set, key=lambda s: s.lower())

    # Write the two main output files
    write_list_to_file(members_path, members_sorted)
    write_list_to_file(no_login_path, no_login_sorted)

    # Build audit log content
    run_time = datetime.now().isoformat(sep=" ", timespec="seconds")
    system_info = f"{platform.system()} {platform.release()} (Python on {platform.platform()})"

    def limit_list(counter_obj, limit=SAMPLE_LIMIT):
        return [k for k, _ in counter_obj.most_common(limit)]

    audit_lines = []
    audit_lines.append(f"Run Date: {run_time}")
    audit_lines.append(f"Script Path: {Path(__file__).resolve()}")
    audit_lines.append(f"System Info: {system_info}")
    audit_lines.append("")
    audit_lines.append("---- High-Level Summary ----")
    audit_lines.append(f"Input file: {input_path.resolve()}")
    audit_lines.append(f"Output directory: {out_dir.resolve()}")
    audit_lines.append(f"Total rows processed: {total_rows}")
    audit_lines.append(f"Unique GitHub Logins found: {len(logins_with_value_set)}")
    audit_lines.append(f"Unique Emails with NO GitHub Login: {len(emails_no_login_set)}")
    audit_lines.append(f"Total unique values written: {len(logins_with_value_set) + len(emails_no_login_set)}")
    audit_lines.append("")
    audit_lines.append("---- Duplicate Summary ----")
    audit_lines.append(f"Duplicate GitHub Logins skipped (unique dup count): {len(duplicate_logins)}")
    if duplicate_logins:
        sample_dup_logins = limit_list(duplicate_logins)
        audit_lines.append("Sample duplicate GH logins skipped:")
        for i, s in enumerate(sample_dup_logins, start=1):
            audit_lines.append(f"  {i}. {s} (skipped {duplicate_logins[s]} extra occurrence(s))")
    else:
        audit_lines.append("No duplicate GH logins found.")

    audit_lines.append("")
    audit_lines.append(f"Duplicate Emails skipped (unique dup count): {len(duplicate_emails)}")
    if duplicate_emails:
        sample_dup_emails = limit_list(duplicate_emails)
        audit_lines.append("Sample duplicate emails skipped:")
        for i, s in enumerate(sample_dup_emails, start=1):
            audit_lines.append(f"  {i}. {s} (skipped {duplicate_emails[s]} extra occurrence(s))")
    else:
        audit_lines.append("No duplicate emails found.")

    audit_lines.append("")
    audit_lines.append("---- Data Quality / Sanity Checks ----")
    audit_lines.append(f"Rows with missing Email while login blank: {rows_missing_email}")
    audit_lines.append(f"Rows where login column likely missing (heuristic): {rows_missing_login_field}")
    audit_lines.append("Malformed / suspicious login examples (limited):")
    if malformed_emails_samples:
        for idx, login_val, email_val in malformed_emails_samples[:SAMPLE_LIMIT]:
            audit_lines.append(f"  Row {idx}: login looks like email -> '{login_val}' (email column: '{email_val}')")
    else:
        audit_lines.append("  None found (sample)")

    audit_lines.append("")
    audit_lines.append("Suspicious login heuristics (contains '@' or spaces) (limited):")
    if suspicious_logins_samples:
        for idx, login_val, email_val in suspicious_logins_samples[:SAMPLE_LIMIT]:
            audit_lines.append(f"  Row {idx}: '{login_val}' (email: '{email_val}')")
    else:
        audit_lines.append("  None found (sample)")

    audit_lines.append("")
    audit_lines.append("---- Blank Value Breakdown (counts by normalized token) ----")
    if blank_breakdown:
        for token, cnt in blank_breakdown.items():
            printable = repr(token)
            audit_lines.append(f"  {printable}: {cnt}")
            if blank_examples[token]:
                for ridx, raw in blank_examples[token][:5]:
                    audit_lines.append(f"    Example Row {ridx}: raw value {repr(raw)}")
    else:
        audit_lines.append("  No blank-style values observed.")

    audit_lines.append("")
    audit_lines.append("---- Files Written ----")
    audit_lines.append(f"Members (unique) -> {members_path.resolve()} (count: {len(members_sorted)})")
    audit_lines.append(f"No-GH-Login Emails (unique) -> {no_login_path.resolve()} (count: {len(no_login_sorted)})")
    audit_lines.append("")
    audit_lines.append("---- End of Audit ----")

    # Write audit log to file
    with audit_log_path.open("w", encoding="utf-8", newline="") as f:
        f.write("\n".join(audit_lines))

    # Print summary to console as well
    print("Processing complete.")
    print(f"  Total rows processed: {total_rows}")
    print(f"  Unique GitHub Logins written: {len(members_sorted)} -> {members_path.resolve()}")
    print(f"  Unique Emails (no login) written: {len(no_login_sorted)} -> {no_login_path.resolve()}")
    print(f"  Audit log: {audit_log_path.resolve()}")


# -------------------------
# CLI
# -------------------------
def main():
    parser = argparse.ArgumentParser(description="Generate AGS audit pack: separate GH logins and emails without login + audit log.")
    parser.add_argument("--input", "-i", type=str, default=DEFAULT_INPUT, help="Input CSV file path (default: gh_login_output.csv)")
    parser.add_argument("--outdir", "-o", type=str, default=".", help="Output directory (default: current directory)")
    args = parser.parse_args()

    input_path = Path(args.input)
    out_dir = Path(args.outdir)

    try:
        process_file(input_path, out_dir)
    except Exception as e:
        print("ERROR:", e)
        raise


if __name__ == "__main__":
    main()

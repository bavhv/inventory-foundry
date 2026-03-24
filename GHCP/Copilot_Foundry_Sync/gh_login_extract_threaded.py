import csv
import os
import requests
import argparse
import time
import logging
import random
import sys
import urllib3

from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock, local

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ==========================
# CONFIGURATION (SAFE DEFAULTS)
# ==========================

MAX_WORKERS = 8                 # Number of parallel threads (start safe)
REQUESTS_PER_SECOND = 5         # API rate limit
MAX_RETRIES = 5                 # Retry attempts per email
BACKOFF_BASE = 1.5              # Exponential backoff base
REQUEST_TIMEOUT = 30            # HTTP timeout in seconds

# ==========================
# GLOBALS
# ==========================

rate_lock = Lock()
last_request_time = 0
thread_local = local()

# ==========================
# LOGGING SETUP
# ==========================

def setup_logging():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = f"1source_fetch_{timestamp}.log"

    logging.basicConfig(
        filename=log_file,
        filemode="w",
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    return log_file

# ==========================
# RATE LIMITER
# ==========================

def rate_limited():
    global last_request_time
    with rate_lock:
        now = time.time()
        min_interval = 1 / REQUESTS_PER_SECOND
        elapsed = now - last_request_time
        if elapsed < min_interval:
            time.sleep(min_interval - elapsed)
        last_request_time = time.time()

# ==========================
# THREAD-LOCAL SESSION
# ==========================

def get_session(username, password):
    if not hasattr(thread_local, "session"):
        session = requests.Session()
        session.verify = False
        session.auth = (username, password)
        thread_local.session = session
    return thread_local.session

# ==========================
# CORE API FUNCTION (RETRY SAFE)
# ==========================

def get_details_from_1source(email, username, password):
    BASE_URL = "https://1source.intel.com/api/inventory/users"
    url = f"{BASE_URL}?page_number=1&page_size=25&filter[email][eq]={email}"
    headers = {"Accept": "application/json"}

    session = get_session(username, password)

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            rate_limited()
            response = session.get(url, headers=headers, timeout=REQUEST_TIMEOUT)

            if response.status_code == 200:
                data = response.json()
                records = data.get("records", [])

                if not records:
                    logging.warning(f"No record found for email: {email}")
                    return email, None, None

                valid_records = [r for r in records if r.get("github_login")]
                enabled_valid = [r for r in valid_records if r.get("enabled")]

                if enabled_valid:
                    enabled_valid.sort(
                        key=lambda x: x.get("github_updated_date") or "",
                        reverse=True
                    )
                    best = enabled_valid[0]
                elif valid_records:
                    valid_records.sort(
                        key=lambda x: x.get("github_updated_date") or "",
                        reverse=True
                    )
                    best = valid_records[0]
                else:
                    records.sort(
                        key=lambda x: x.get("updated_date") or "",
                        reverse=True
                    )
                    best = records[0]

                return (
                    best.get("email"),
                    best.get("wwid"),
                    best.get("github_login")
                )

            elif response.status_code == 429:
                wait = BACKOFF_BASE ** attempt + random.uniform(0, 1)
                logging.warning(
                    f"429 Rate limit for {email}, "
                    f"retry {attempt}/{MAX_RETRIES}, sleeping {wait:.2f}s"
                )
                time.sleep(wait)

            elif 500 <= response.status_code < 600:
                wait = BACKOFF_BASE ** attempt
                logging.warning(
                    f"Server error {response.status_code} for {email}, "
                    f"retrying in {wait:.2f}s"
                )
                time.sleep(wait)

            else:
                logging.error(
                    f"{email} | HTTP {response.status_code} | {response.text}"
                )
                return email, None, None

        except requests.RequestException as e:
            wait = BACKOFF_BASE ** attempt
            logging.warning(
                f"Request exception for {email}, "
                f"retry {attempt}/{MAX_RETRIES}, sleeping {wait:.2f}s | {e}"
            )
            time.sleep(wait)

    logging.error(f"Max retries exceeded for {email}")
    return email, None, None

# ==========================
# FILE PROCESSING (PARALLEL)
# ==========================

def process_file(input_file, output_file, username, password):
    logging.info(f"Processing input file: {input_file}")

    if not os.path.exists(input_file):
        raise FileNotFoundError(f"Input file not found: {input_file}")

    with open(input_file, "r") as infile:
        emails = [line.strip() for line in infile if line.strip()]

    logging.info(f"Total emails to process: {len(emails)}")

    csv_lock = Lock()

    with open(output_file, "w", newline="") as outfile:
        writer = csv.writer(outfile)
        writer.writerow(["Email", "WWID", "GitHub Login"])

        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = {
                executor.submit(
                    get_details_from_1source,
                    email,
                    username,
                    password
                ): email
                for email in emails
            }

            completed = 0
            for future in as_completed(futures):
                email = futures[future]
                try:
                    result = future.result()
                except Exception:
                    logging.exception(f"Unhandled exception for {email}")
                    result = (email, None, None)

                with csv_lock:
                    writer.writerow(result)

                completed += 1
                if completed % 100 == 0 or completed == len(emails):
                    percent = (completed / len(emails)) * 100
                    msg = (
                        f"\rProcessed {completed}/{len(emails)} "
                        f"({percent:.2f}%)"
                    )
                    sys.stdout.write(msg)
                    sys.stdout.flush()

                    logging.info(
                        f"Progress: {completed}/{len(emails)} "
                        f"({percent:.2f}%)"
                    )

# ==========================
# MAIN
# ==========================

if __name__ == "__main__":

    log_file = setup_logging()
    start_time = time.time()
    start_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    logging.info("=" * 70)
    logging.info(f"Script started at : {start_ts}")
    logging.info(f"Log file         : {log_file}")
    logging.info("=" * 70)

    parser = argparse.ArgumentParser(
        description="Fetch WWID & GitHub Login by Email from 1Source API"
    )
    parser.add_argument("--username", default=os.getenv("LDAPUSERNAME"), help="1Source username")
    parser.add_argument("--password", default=os.getenv("LDAPPASSWORD"), help="1Source password")
    parser.add_argument("--input", default="ags_emails.txt", help="Input email file")
    parser.add_argument("--output", default="gh_login_output.csv", help="Output CSV file")

    args = parser.parse_args()

    if not args.username or not args.password:
        raise SystemExit("❌ Username or password not provided (CLI or ENV)")

    process_file(
        args.input,
        args.output,
        args.username,
        args.password
    )

    end_time = time.time()
    end_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    total_seconds = int(end_time - start_time)
    h, rem = divmod(total_seconds, 3600)
    m, s = divmod(rem, 60)

    logging.info("=" * 70)
    logging.info(f"Script ended at   : {end_ts}")
    logging.info(f"Total run time   : {h:02d}:{m:02d}:{s:02d} (HH:MM:SS)")
    logging.info("=" * 70)

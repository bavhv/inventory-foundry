#!/usr/bin/env python3
import os
import requests
import logging
from datetime import datetime

# ============================
# User Configurable Variables
# ============================
ORG = "Copilot-Management-For-Foundry"
TEAM_SLUG = "copilot-business-user-foundry"
ALL_USERS_TEAM_SLUG = "1source-all-users"

ALL_USERS_FILE = "1source_all_users.txt"
NOT_IN_ALL_USERS_FILE = "not_in_1source_all_users.txt"

ADD_FILE = "only_in_AGS.txt"
REMOVE_FILE = "only_in_GH_Teams.txt"

# Proxy Configuration (as provided)
PROXIES = {
    "http": "http://proxy-dmz.intel.com:912",
    "https": "http://proxy-dmz.intel.com:912",
    "no_proxy": "intel.com,.intel.com,localhost,127.0.0.1"
}

# ============================
# Setup Logging (UTF-8 Safe)
# ============================
log_filename = f"team_user_updates_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(log_filename, encoding="utf-8"),
        logging.StreamHandler(stream=os.sys.stdout)
    ]
)

# ============================
# Authentication
# ============================
TOKEN = os.getenv("GITHUB_TOKEN")
if not TOKEN:
    logging.error("❌ ERROR: Environment variable GITHUB_TOKEN not set.")
    exit(1)

# ============================
# Dry Run Configuration
# ============================
DRY_RUN = os.getenv("DRY_RUN", "false").lower() == "true"

if DRY_RUN:
    logging.warning("🟡 DRY-RUN MODE ENABLED — No changes will be made to GitHub teams")

HEADERS = {
    "Accept": "application/vnd.github+json",
    "Authorization": f"Bearer {TOKEN}",
    "X-GitHub-Api-Version": "2022-11-28"
}

# ============================
# Helper Function
# ============================
def read_users_from_file(filename):
    if not os.path.exists(filename):
        logging.warning(f"⚠️ File not found: {filename}. Skipping.")
        return []
    with open(filename, "r") as f:
        return [line.strip() for line in f if line.strip()]

# ============================
# Helper: Get users from a GitHub team (with pagination)
# ============================
def fetch_team_members(team_slug, output_file):
    """
    Fetch all members of a GitHub team and save to a file.
    Returns a set of usernames.
    """
    members = set()
    page = 1
    per_page = 100

    logging.info(f"🔍 Fetching members from team: {team_slug}")

    while True:
        url = f"https://api.github.com/orgs/{ORG}/teams/{team_slug}/members"
        params = {"page": page, "per_page": per_page}

        response = requests.get(
            url,
            headers=HEADERS,
            proxies=PROXIES,
            params=params
        )

        if response.status_code != 200:
            logging.error(
                f"❌ Failed to fetch members from {team_slug}. "
                f"HTTP {response.status_code}: {response.text}"
            )
            break

        data = response.json()
        if not data:
            break

        for user in data:
            members.add(user["login"])

        page += 1

    # Save to file
    with open(output_file, "w", encoding="utf-8") as f:
        for user in sorted(members):
            f.write(f"{user}\n")

    logging.info(f"📄 Saved {len(members)} users to {output_file}")
    return members

# ============================
# Helper: Write users not eligible for add
# ============================

def write_not_in_all_users(username):
    with open(NOT_IN_ALL_USERS_FILE, "a", encoding="utf-8") as f:
        f.write(f"{username}\n")

# ============================
# Add User to Team
# ============================
def add_user(username):
    if DRY_RUN:
        logging.info(f"[DRY-RUN] Would ADD user: {username}")
        return
    
    url = f"https://api.github.com/orgs/{ORG}/teams/{TEAM_SLUG}/memberships/{username}"
    response = requests.put(url, headers=HEADERS, proxies=PROXIES)

    if response.status_code in [200, 201]:
        logging.info(f"✅ ADDED: {username} → {response.json().get('state')}")
    else:
        logging.error(f"❌ FAILED to add {username}. HTTP {response.status_code}. Response: {response.text}")

# ============================
# Remove User from Team
# ============================
def remove_user(username):
    if DRY_RUN:
        logging.info(f"[DRY-RUN] Would REMOVE user: {username}")
        return
    
    url = f"https://api.github.com/orgs/{ORG}/teams/{TEAM_SLUG}/memberships/{username}"
    response = requests.delete(url, headers=HEADERS, proxies=PROXIES)

    if response.status_code in [200, 204]:
        logging.info(f"🗑️ REMOVED: {username}")
    else:
        logging.error(f"❌ FAILED to remove {username}. HTTP {response.status_code}. Response: {response.text}")

# ============================
# Main Execution
# ============================
def main():
    logging.info("🔵 GitHub Team Management Script Started")

    users_to_add = read_users_from_file(ADD_FILE)
    users_to_remove = read_users_from_file(REMOVE_FILE)

    logging.info(f"📍 ORG: {ORG}, TEAM: {TEAM_SLUG}")
    logging.info(f"📥 Users to Add: {len(users_to_add)}")
    logging.info(f"🧹 Users to Remove: {len(users_to_remove)}")

    # # 🔑 NEW STEP: Fetch baseline team users
    # all_users_team_members = fetch_team_members(
    #     ALL_USERS_TEAM_SLUG,
    #     ALL_USERS_FILE
    # )

    # # Clear previous not-eligible file (fresh run)
    # if os.path.exists(NOT_IN_ALL_USERS_FILE):
    #     os.remove(NOT_IN_ALL_USERS_FILE)

    # 🔁 Controlled add logic
    for user in users_to_add:
        logging.info(f"✅ Proceeding to add {user} in {TEAM_SLUG} Teams.")
        add_user(user)
        
    # for user in users_to_remove:
    #     remove_user(user)

    logging.info("✅ Script execution completed.")
    logging.info(f"📄 Log saved to: {log_filename}")



if __name__ == "__main__":
    main()

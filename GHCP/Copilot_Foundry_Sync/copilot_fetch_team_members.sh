#!/bin/bash

ORG="intel-innersource"
TEAM_SLUG="1source-github-copilot-business-user"
OUTPUT_FILE="team_members.txt"

export http_proxy="http://proxy-dmz.intel.com:912"
export https_proxy="http://proxy-dmz.intel.com:912"
export no_proxy="intel.com,.intel.com,localhost,127.0.0.1"

# Read token from environment
if [[ -z "${TOKEN:-}" ]]; then
  echo "❌ ERROR: GITHUB_TOKEN environment variable not set"
  exit 1
fi

page=1
> "$OUTPUT_FILE"

echo "Fetching members from team: $TEAM_SLUG ..."

while true; do
  response=$(curl -s -H "Accept: application/vnd.github+json" \
	  -H "Authorization: Bearer $TOKEN" \
	  -H "X-GitHub-Api-Version: 2022-11-28" \
    "https://api.github.com/orgs/$ORG/teams/$TEAM_SLUG/members?per_page=100&page=$page")

  logins=$(echo "$response" | jq -r '.[].login')

  # Break if no data returned
  [[ -z "$logins" ]] && break

  echo "$logins" >> "$OUTPUT_FILE"
  page=$((page+1))
done

total=$(wc -l < "$OUTPUT_FILE")

echo "✅ Total Members: $total"
echo "📄 Saved login names to: $OUTPUT_FILE"


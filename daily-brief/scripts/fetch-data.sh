#!/usr/bin/env bash
# fetch-data.sh — Helper for daily-brief skill
# Sources env vars, queries Directus and Composio, outputs JSON
set -euo pipefail

# Load env
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ENV_FILE="$SCRIPT_DIR/../.env"
[ -f "$ENV_FILE" ] && source "$ENV_FILE"

# Ensure required vars
: "${DIRECTUS_URL:?DIRECTUS_URL not set}"
: "${DIRECTUS_TOKEN:?DIRECTUS_TOKEN not set}"

echo "{" > /tmp/daily-brief-data.json

# Goals
echo '"goals": ' >> /tmp/daily-brief-data.json
curl -s --max-time 10 "$DIRECTUS_URL/items/timetracker_goals?access_token=$DIRECTUS_TOKEN&limit=200" >> /tmp/daily-brief-data.json
echo ',' >> /tmp/daily-brief-data.json

# Tasks
echo '"tasks": ' >> /tmp/daily-brief-data.json
curl -s --max-time 10 "$DIRECTUS_URL/items/timetracker_tasks?access_token=$DIRECTUS_TOKEN&limit=200&sort[]=-updatedAt&meta=total_count" >> /tmp/daily-brief-data.json
echo ',' >> /tmp/daily-brief-data.json

# Habits
echo '"habits": ' >> /tmp/daily-brief-data.json
curl -s --max-time 10 "$DIRECTUS_URL/items/timetracker_habits?access_token=$DIRECTUS_TOKEN&limit=100" >> /tmp/daily-brief-data.json
echo ',' >> /tmp/daily-brief-data.json

# Habit logs
echo '"habit_logs": ' >> /tmp/daily-brief-data.json
curl -s --max-time 10 "$DIRECTUS_URL/items/timetracker_habit_logs?access_token=$DIRECTUS_TOKEN&limit=100&sort[]=-date" >> /tmp/daily-brief-data.json

echo '}' >> /tmp/daily-brief-data.json

jq . /tmp/daily-brief-data.json 2>/dev/null || cat /tmp/daily-brief-data.json

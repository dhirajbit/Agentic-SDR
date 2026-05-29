#!/usr/bin/env bash
# Deploy the Best Roadways SDR dashboard to Cloudflare Pages.
#
#   tenants/best-roadways/deploy_dashboard.sh
#
# Reads CLOUDFLARE_API_TOKEN / CLOUDFLARE_ACCOUNT_ID / CLOUDFLARE_PAGES_PROJECT
# from tenants/best-roadways/.env. Never deploys without an explicit invocation.

set -euo pipefail

TENANT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$TENANT_DIR/../.." && pwd)"
cd "$REPO_ROOT"

set -a
# shellcheck disable=SC1091
source "$TENANT_DIR/.env"
set +a

: "${CLOUDFLARE_API_TOKEN:?CLOUDFLARE_API_TOKEN not set in tenant .env}"
: "${CLOUDFLARE_ACCOUNT_ID:?CLOUDFLARE_ACCOUNT_ID not set in tenant .env}"
: "${CLOUDFLARE_PAGES_PROJECT:?CLOUDFLARE_PAGES_PROJECT not set in tenant .env}"

HTML="$TENANT_DIR/sdr_dashboard.html"
if [[ ! -f "$HTML" ]]; then
  echo "ERROR: $HTML not found. Run generate_dashboard.py first." >&2
  exit 1
fi

STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT
cp "$HTML" "$STAGE/index.html"

echo "Deploying to Cloudflare Pages project: $CLOUDFLARE_PAGES_PROJECT"
echo "  account: $CLOUDFLARE_ACCOUNT_ID"
echo "  source : $HTML ($(wc -c < "$HTML" | tr -d ' ') bytes)"

npx --yes wrangler@latest pages deploy "$STAGE" \
  --project-name="$CLOUDFLARE_PAGES_PROJECT" \
  --commit-dirty=true

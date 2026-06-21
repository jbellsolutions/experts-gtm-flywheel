#!/usr/bin/env bash
# Sync SYSTEM code from an internal brand deployment into this public template.
#
#   scripts/sync_from_internal.sh /path/to/internal-repo
#
# The internal repo (e.g. your most-developed brand build) is the source of truth
# for system code. This pulls the system files in, leaves the template-owned brand
# files untouched, scrubs IDs + brand phrasing, then leak-checks. Review the diff
# before committing. See docs/SYNC.md for the model + limitations.
set -euo pipefail

SRC="${1:?usage: scripts/sync_from_internal.sh /path/to/internal-repo}"
DEST="$(cd "$(dirname "$0")/.." && pwd)"
[ -d "$SRC/agents/content_flywheel" ] || { echo "ERROR: $SRC is not a flywheel repo"; exit 1; }

# Files the template OWNS — never overwrite from the internal repo (brand/template content).
EXCLUDES=(
  --exclude='.git' --exclude='node_modules' --exclude='.next' --exclude='__pycache__'
  --exclude='.env' --exclude='.env.*'
  --exclude='**/brand_voice.py'
  --exclude='**/voices.py'
  --exclude='**/voice_banks/**'
  --exclude='**/leadgen-offers.ts'
  --exclude='**/leads/page.tsx'
  --exclude='**/smartlead_setup.py'
  --exclude='**/airtable_setup.py'
  --exclude='**/build_readme_assets.py'
)

# System paths to pull (everything else is template/brand/docs, left alone).
PATHS=(
  agents shared workflows extension
  dashboard/app dashboard/components dashboard/lib
  Dockerfile.worker Dockerfile.browser-runner Dockerfile.api
  requirements.txt railway.json scripts/run_supabase_migration.py
)

echo "Syncing system code:  $SRC  ->  $DEST"
for p in "${PATHS[@]}"; do
  [ -e "$SRC/$p" ] || continue
  if [ -d "$SRC/$p" ]; then
    mkdir -p "$DEST/$p"
    rsync -a "${EXCLUDES[@]}" "$SRC/$p/" "$DEST/$p/"
  else
    rsync -a "${EXCLUDES[@]}" "$SRC/$p" "$DEST/$p"
  fi
done
echo "  ...synced."
echo

# Scrub hard-coded IDs + brand phrasing out of the freshly-synced system files,
# then fail loudly if any brand/secret residue remains.
python3 "$DEST/scripts/_scrub_template.py"

echo
echo "Next: review 'git diff'. If the internal repo changed the STRUCTURE of a"
echo "template-owned file (brand_voice.py, voices.py, voice_banks/, leadgen-offers.ts,"
echo "the leads page, or the setup scripts), reconcile that by hand — those are not"
echo "auto-synced on purpose. See docs/SYNC.md."

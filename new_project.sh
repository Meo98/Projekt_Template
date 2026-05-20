#!/usr/bin/env bash
# Creates a new Pico project repo from this template and configures it fully.
#
# Prerequisites:
#   1. gh CLI installed and logged in (gh auth login)
#   2. NOTION_TOKEN set in your environment, e.g. in ~/.zshrc:
#      export NOTION_TOKEN="ntn_..."
#
# Usage:
#   ./new_project.sh MyProjectName [--public]

set -euo pipefail

PROJECT_NAME="${1:?Usage: $0 <ProjectName> [--public]}"
VISIBILITY="--private"
[[ "${2:-}" == "--public" ]] && VISIBILITY="--public"

GITHUB_USER="$(gh api user --jq .login)"
REPO="$GITHUB_USER/$PROJECT_NAME"

echo "Creating repo $REPO from template Meo98/Pico_Template..."
gh repo create "$REPO" \
  --template "Meo98/Pico_Template" \
  $VISIBILITY \
  --clone

echo "Setting NOTION_TOKEN secret..."
if [[ -z "${NOTION_TOKEN:-}" ]]; then
  echo "  NOTION_TOKEN not set in environment."
  echo "  Add this to your ~/.zshrc and restart the shell:"
  echo "    export NOTION_TOKEN=\"ntn_...\""
  echo "  Then run manually:"
  echo "    gh secret set NOTION_TOKEN --repo $REPO"
else
  gh secret set NOTION_TOKEN --repo "$REPO" --body "$NOTION_TOKEN"
  echo "  Secret set."
fi

echo "Creating Notion project entry..."
if [[ -n "${NOTION_TOKEN:-}" ]]; then
  GITHUB_URL="https://github.com/$REPO"
  PROJEKTE_DB="359d2e49b98481fb83c2e2e3f1a9edbb"
  DISPLAY_NAME="${PROJECT_NAME//_/ }"

  RESPONSE=$(curl -s -X POST "https://api.notion.com/v1/pages" \
    -H "Authorization: Bearer $NOTION_TOKEN" \
    -H "Content-Type: application/json" \
    -H "Notion-Version: 2022-06-28" \
    -d "{
      \"parent\": {\"database_id\": \"$PROJEKTE_DB\"},
      \"properties\": {
        \"Name\": {\"title\": [{\"text\": {\"content\": \"$DISPLAY_NAME\"}}]},
        \"Status\": {\"select\": {\"name\": \"In Arbeit\"}},
        \"GitHub URL\": {\"url\": \"$GITHUB_URL\"}
      }
    }")

  if echo "$RESPONSE" | grep -q '"object":"page"'; then
    echo "  Notion project page created."
  else
    echo "  Notion: $(echo "$RESPONSE" | grep -o '"message":"[^"]*"' | head -1)"
  fi
else
  echo "  Skipped (NOTION_TOKEN not set)."
fi

echo ""
echo "Done! Project created at: https://github.com/$REPO"
echo ""
echo "Next steps:"
echo "  cd $PROJECT_NAME"
echo "  Rename hardware/kicad/Template.* to hardware/kicad/$PROJECT_NAME.*"
echo "  Edit firmware/pico_config.py with your pin assignments"
echo "  Optional: hardware/cad/case.scad — board dimensions eintragen für Gehäuse"

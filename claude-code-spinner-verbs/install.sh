#!/usr/bin/env bash
set -euo pipefail

PACKS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/packs" && pwd)"
SETTINGS_FILE="${CLAUDE_SETTINGS:-$HOME/.claude/settings.json}"

usage() {
  cat <<EOF
Usage:
  ./install.sh --list
  ./install.sh <pack> [--mode replace|append] [--preview]

Options:
  --list          Show available packs
  --mode          replace (only pack verbs) or append (merge with existing) [default: append]
  --preview       Print resulting config without writing

Examples:
  ./install.sh cassino
  ./install.sh naruto --mode replace
  ./install.sh filosofo-dev --preview
EOF
  exit 1
}

list_packs() {
  echo ""
  echo "Available packs:"
  echo ""
  for file in "$PACKS_DIR"/*.json; do
    local name description verb_count
    name=$(python3 -c "import json,sys; d=json.load(open('$file')); print(d['name'])")
    description=$(python3 -c "import json,sys; d=json.load(open('$file')); print(d['description'])")
    verb_count=$(python3 -c "import json,sys; d=json.load(open('$file')); print(len(d['verbs']))")
    printf "  %-20s %s (%s verbs)\n" "$name" "$description" "$verb_count"
  done
  echo ""
}

install_pack() {
  local pack_name="$1"
  local mode="${2:-append}"
  local preview="${3:-false}"
  local pack_file="$PACKS_DIR/$pack_name.json"

  if [[ ! -f "$pack_file" ]]; then
    echo "Error: pack '$pack_name' not found in $PACKS_DIR"
    echo "Run ./install.sh --list to see available packs"
    exit 1
  fi

  if [[ ! -f "$SETTINGS_FILE" ]]; then
    echo "Error: settings file not found at $SETTINGS_FILE"
    exit 1
  fi

  python3 - "$pack_file" "$SETTINGS_FILE" "$mode" "$preview" <<'PYTHON'
import json, sys

pack_file, settings_file, mode, preview_flag = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]

with open(pack_file) as f:
    pack = json.load(f)

with open(settings_file) as f:
    settings = json.load(f)

pack_verbs = pack["verbs"]
existing_verbs = settings.get("spinnerVerbs", {}).get("verbs", [])

if mode == "replace":
    final_verbs = pack_verbs
elif mode == "append":
    seen = set(existing_verbs)
    new_verbs = [v for v in pack_verbs if v not in seen]
    final_verbs = existing_verbs + new_verbs
else:
    print(f"Error: unknown mode '{mode}'. Use replace or append.")
    sys.exit(1)

settings["spinnerVerbs"] = {"mode": mode, "verbs": final_verbs}

output = json.dumps(settings, indent=2, ensure_ascii=False)

if preview_flag == "true":
    verbs_preview = json.dumps({"spinnerVerbs": settings["spinnerVerbs"]}, indent=2, ensure_ascii=False)
    print("\nPreview — spinnerVerbs block that would be written:\n")
    print(verbs_preview)
    print(f"\nTotal verbs: {len(final_verbs)} ({len(pack_verbs)} from pack, mode: {mode})")
else:
    with open(settings_file, "w") as f:
        f.write(output + "\n")
    print(f"Installed '{pack['name']}' ({len(pack_verbs)} verbs, mode: {mode}) into {settings_file}")
    print(f"Total spinner verbs now: {len(final_verbs)}")
    print("Run /clear or start a new session to apply.")
PYTHON
}

[[ $# -eq 0 ]] && usage

PACK_NAME=""
MODE="append"
PREVIEW="false"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --list) list_packs; exit 0 ;;
    --mode) MODE="$2"; shift 2 ;;
    --preview) PREVIEW="true"; shift ;;
    --help|-h) usage ;;
    -*) echo "Unknown option: $1"; usage ;;
    *) PACK_NAME="$1"; shift ;;
  esac
done

[[ -z "$PACK_NAME" ]] && usage

install_pack "$PACK_NAME" "$MODE" "$PREVIEW"

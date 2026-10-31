#!/usr/bin/env bash
# Rerun the official verifier on the committed public synthetic archive.
set -euo pipefail

ROOT=/mnt/c/Users/mailp/OneDrive/Desktop/VVT
TOOL=/root/.local/share/votevault-belenios-3.3.0/_run/tool-debug/bin/belenios-tool
VERIFY_DIR=/root/.local/share/votevault-verify-exact
ARCHIVE="$ROOT/docs/belenios-real-synthetic/election.bel"
OUTPUT="$ROOT/docs/belenios-real-synthetic/official-verifier-rerun.txt"

test -x "$TOOL"
mkdir -p "$VERIFY_DIR"
cp "$ARCHIVE" "$VERIFY_DIR/election.bel"
cmp --silent "$ARCHIVE" "$VERIFY_DIR/election.bel"
sha256sum "$ARCHIVE" "$VERIFY_DIR/election.bel"
(cd "$VERIFY_DIR" && "$TOOL" election verify) > "$OUTPUT" 2>&1
cat "$OUTPUT"

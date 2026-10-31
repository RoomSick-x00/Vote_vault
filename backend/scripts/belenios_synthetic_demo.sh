#!/usr/bin/env bash
# Real Belenios 3.3.0 demonstration. Synthetic voters and choices only.
# Usage: bash belenios_synthetic_demo.sh /absolute/path/to/belenios-tool /new/output/directory
# Work files contain synthetic private credentials and trustee keys in /tmp;
# the output directory contains only public election archives and logs.
set -euo pipefail
export BELENIOS_USE_URANDOM=1
umask 077
TOOL=$(realpath "$1")
OUT=$2
mkdir "$OUT"
OUT=$(realpath "$OUT")
WORK=$(mktemp -d /tmp/votevault-synthetic.XXXXXXXX)
exec > >(tee "$OUT/demo-output.txt") 2>&1
echo 'Belenios 3.3.0: synthetic one-voter, two-candidate election'
cd "$WORK"
UUID=$("$TOOL" setup generate-token)
echo "Election UUID: $UUID"
cat > questions.json <<'JSON'
{"description":"Synthetic campus election","name":"Synthetic election","questions":[{"answers":["Candidate A","Candidate B"],"min":1,"max":1,"question":"Choose one representative"}]}
JSON
"$TOOL" setup generate-credentials --uuid "$UUID" --group Ed25519 --count 1
mv -- *.pubcreds public_creds.json
mv -- *.privcreds private_creds.json
jq -r 'to_entries[0].value' private_creds.json > voter.credential
"$TOOL" setup generate-trustee-key --group Ed25519
cat -- *.pubkey > public_keys.jsons
"$TOOL" setup make-trustees
"$TOOL" setup make-election --uuid "$UUID" --group Ed25519 --template questions.json
"$TOOL" archive init
printf '[[1,0]]\n' > choice.json
"$TOOL" election generate-ballot --privcred voter.credential --choice choice.json > ballot.json
"$TOOL" election verify-ballot --ballot ballot.json
# generate-ballot adds a newline, while Belenios hashes canonical ballot bytes.
BALLOT=$(cat ballot.json)
TRACKER=$(printf '%s' "$BALLOT" | "$TOOL" sha256-b64)
echo "Ballot tracker: $TRACKER"
printf '%s\n' "$BALLOT" | "$TOOL" archive add-event --type=Ballot
mkdir duplicate
cp "$UUID.bel" duplicate/
printf '[[0,1]]\n' > choice.json
"$TOOL" election generate-ballot --privcred voter.credential --choice choice.json > duplicate-ballot.json
DUPLICATE=$(cat duplicate-ballot.json)
(cd duplicate; printf '%s\n' "$DUPLICATE" | "$TOOL" archive add-event --type=Ballot)

"$TOOL" archive add-event --type=EndBallots < /dev/null
cp "$UUID.bel" "$OUT/missing-tally.bel"
"$TOOL" election verify > "$OUT/missing-tally-official.txt" 2>&1

TRUSTEE=$(printf '%s\n' ./*.privkey)
finish() {
    "$TOOL" election compute-encrypted-tally | "$TOOL" archive add-event --type=EncryptedTally
    "$TOOL" election decrypt --privkey "$TRUSTEE" --trustee-id 1 | "$TOOL" archive add-event --type=PartialDecryption
    "$TOOL" election compute-result | "$TOOL" archive add-event --type=Result
}
finish
"$TOOL" election verify > "$OUT/official-verifier.txt" 2>&1
cp "$UUID.bel" "$OUT/election.bel"
(
    cd duplicate
    "$TOOL" archive add-event --type=EndBallots < /dev/null
    # Private trustee key remains in the synthetic work directory.
    TRUSTEE="../$TRUSTEE"
    finish
    "$TOOL" election verify > "$OUT/duplicate-official.txt" 2>&1
    cp "$UUID.bel" "$OUT/duplicate-credential.bel"
)
printf '%s\n' "$UUID" > "$OUT/election-id.txt"
printf '%s\n' "$TRACKER" > "$OUT/receipt.txt"
echo 'Official verifier output:'
cat "$OUT/official-verifier.txt"
echo "Synthetic private working files retained at $WORK"
echo "Public artifacts saved at $OUT"

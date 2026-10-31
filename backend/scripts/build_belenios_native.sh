#!/usr/bin/env bash
# Isolated native Belenios 3.3.0 build. Linux/WSL; synthetic research only.
# Requires the upstream source checkout at the path below, OPAM 2.5.1 whose
# official release SHA-256 is checked below, and Belenios's system packages.
set -euo pipefail
SOURCE=/root/.local/share/votevault-belenios-3.3.0
SYSROOT=/root/.local/share/votevault-belenios-native
OPAM=/root/.local/share/votevault-opam-2.5.1
EXPECTED_OPAM=33705e328d9f740026ce182079e2457639791bcf04a0e4bafbdb2024dd4d6092
EXPECTED_SOURCE=337887bd1862c7cd057080b530fd80941bfc3c69
REPO_REVISION=045748b2d8c25925135981a8892305b10706ca06
test "$(sha256sum "$OPAM" | cut -d' ' -f1)" = "$EXPECTED_OPAM"
test "$(git -C "$SOURCE" rev-parse HEAD)" = "$EXPECTED_SOURCE"
if test -e "$SYSROOT"; then
    echo "Refusing to replace existing build directory: $SYSROOT" >&2
    exit 1
fi
mkdir -p "$SYSROOT/repository"
git -C "$SYSROOT/repository" init
git -C "$SYSROOT/repository" remote add origin https://github.com/ocaml/opam-repository.git
git -C "$SYSROOT/repository" fetch --depth=1 origin "$REPO_REVISION:opam"
git -C "$SYSROOT/repository" checkout opam
export OPAMROOT="$SYSROOT/opam" XDG_CACHE_HOME="$SYSROOT/cache" OPAMYES=1 OPAMJOBS=4
"$OPAM" init --bare --no-setup -k git "$SYSROOT/repository"
"$OPAM" switch create 5.4.1 ocaml-base-compiler.5.4.1
eval "$("$OPAM" env --switch=5.4.1)"
"$OPAM" repository add --yes belenios-overlay "$SOURCE/vendor/opam-overlay"
# Native CLI dependencies only. Browser/server packages are intentionally not
# claimed as installed; Belenios's upstream bootstrap reports separate failures.
"$OPAM" install --yes base64 hex dune atdgen cryptokit cmdliner lwt.5.9.1 cohttp-lwt-unix yojson re digestif zarith
cd "$SOURCE"
make build-debug-tool
echo "Native verifier: $SOURCE/_run/tool-debug/bin/belenios-tool"

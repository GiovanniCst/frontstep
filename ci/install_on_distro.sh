#!/usr/bin/env bash
# The README's instructions, executed on a real distribution.
#
# They were wrong, and for longer than anybody noticed: the first line said
# `uv tool install frontstep`, naming a package that does not exist on PyPI, and
# the fallbacks assumed a `pip` that most distributions do not ship. Measured in
# August 2026 on stock images: Debian 13 and Ubuntu 24.04 have python3 without
# `pip` AND without `ensurepip`, so even `python3 -m venv` fails; Fedora and Arch
# base images have no Python at all.
#
# So the instructions do not start from Python. `uv` is one static binary that
# brings its own interpreter, which is why it works the same on all of them —
# and this script is what keeps that a fact.
#
# Usage: ci/install_on_distro.sh <docker image> [curl install command]
set -euo pipefail

IMAGE="${1:?an image is needed, e.g. debian:13}"
REPO="$(cd "$(dirname "$0")/.." && pwd)"

# Getting curl is the distribution's business, not ours: it is how uv's own
# published instructions start, and every desktop has it.
case "$IMAGE" in
  debian*|ubuntu*)     GET_CURL="apt-get update && apt-get install -y curl" ;;
  fedora*)             GET_CURL="dnf install -y curl" ;;
  arch*)               GET_CURL="pacman -Sy --noconfirm curl" ;;
  # ⚠️ gawk, and it is not about us: the openSUSE base image has no `awk`, and
  # uv's own install script uses it to check the checksum it just downloaded.
  # Every desktop has awk; a container this bare does not.
  opensuse*)           GET_CURL="zypper -n in curl gawk" ;;
  alpine*)             GET_CURL="apk add --no-cache curl" ;;
  *)                   GET_CURL="true" ;;
esac

# The package comes from the CHECKOUT, not from the published zip: this has to
# fail on the commit that breaks it, not one release later.
docker run --rm -v "$REPO:/src:ro" "$IMAGE" sh -c "
  set -e
  { $GET_CURL ; } >/dev/null 2>&1
  curl -LsSf https://astral.sh/uv/install.sh | sh > /dev/null
  export PATH=\$HOME/.local/bin:\$PATH

  uv tool install /src

  # It has to be on PATH under its own name — 'installed but not runnable' is
  # exactly what a clean Windows showed us, and it counts as not installed.
  command -v frontstep > /dev/null
  frontstep --version

  # And it has to start on a machine with no configuration and no desktop.
  # \`doctor\` exits non-zero only for what actually stops it working, and a
  # runner without a terminal is not a broken machine.
  frontstep doctor
"

#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

grep -Eq '^[[:space:]]*python-multipart([<>=!~].*)?[[:space:]]*$' "${REPO_ROOT}/requirements.txt"

#!/usr/bin/env bash
# Apply autonomy Dockerfile + extended sandbox policy from this deploy bundle into a local NemoClaw clone.
# Usage (on the EC2 host or any machine with the clone):
#   bash apply-nemoclaw-autonomy-to-clone.sh [/path/to/NemoClaw-clone]
#
# Patch files are read from the parent of this script (deploy/nemoclaw-aws-ec2).
# Default clone: ~/.nemoclaw/source
set -euo pipefail

PATCH_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CLONE="${1:-${HOME}/.nemoclaw/source}"

if [[ ! -f "${PATCH_ROOT}/NemoClaw/Dockerfile" ]]; then
  echo "Missing ${PATCH_ROOT}/NemoClaw/Dockerfile" >&2
  exit 1
fi
if [[ ! -d "${CLONE}/nemoclaw" || ! -d "${CLONE}/scripts" ]]; then
  echo "Clone at ${CLONE} does not look like NemoClaw repo root (expected nemoclaw/ and scripts/)." >&2
  exit 1
fi

cp "${PATCH_ROOT}/NemoClaw/Dockerfile" "${CLONE}/Dockerfile"
mkdir -p "${CLONE}/nemoclaw-blueprint/policies"
cp "${PATCH_ROOT}/nemoclaw-blueprint/policies/openclaw-sandbox.yaml" \
  "${CLONE}/nemoclaw-blueprint/policies/openclaw-sandbox.yaml"

echo "Updated:"
echo "  ${CLONE}/Dockerfile"
echo "  ${CLONE}/nemoclaw-blueprint/policies/openclaw-sandbox.yaml"
echo ""
echo "Recreate sandbox (example):"
echo "  export PATH=\"\${HOME}/.local/bin:\${PATH}\""
echo "  openshell sandbox delete my-assistant   # or your sandbox name"
echo "  openshell sandbox create --from \"${CLONE}/Dockerfile\" --name my-assistant \\"
echo "    --policy \"${CLONE}/nemoclaw-blueprint/policies/openclaw-sandbox.yaml\" -- nemoclaw-start"

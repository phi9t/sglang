#!/bin/bash
set -eu -o pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly SCRIPT_DIR

SPACK_PY="/opt/spack_store/view/bin/python3"
if [[ -x "${SPACK_PY}" ]]; then
    PYTHON_BIN="${SPACK_PY}"
else
    PYTHON_BIN="$(command -v python3 2>/dev/null || echo python3)"
fi

SPACK_OWNED_CONF=""
for candidate in \
    "${SCRIPT_DIR}/spack_owned_packages.conf" \
    /opt/container_entrypoints/spack_owned_packages.conf; do
    if [[ -f "${candidate}" ]]; then
        SPACK_OWNED_CONF="${candidate}"
        break
    fi
done

NVIDIA_OVERRIDES=""
for candidate in \
    "${SCRIPT_DIR}/nvidia_overrides.txt" \
    /opt/container_entrypoints/nvidia_overrides.txt; do
    if [[ -f "${candidate}" ]]; then
        NVIDIA_OVERRIDES="${candidate}"
        break
    fi
done

if [[ $# -lt 1 ]]; then
    echo "Usage: uv-install.sh <package> [package ...]" >&2
    exit 2
fi

export PATH="/usr/local:/usr/local/bin:${PATH}"
unset PYTHONPATH

if ! command -v uv >/dev/null 2>&1; then
    echo "ERROR: uv is required in PATH" >&2
    exit 1
fi

VENV_DIR="${VENV_DIR:-.venv}"
CONSTRAINTS_FILE="${CONSTRAINTS_FILE:-/tmp/spack-constraints.txt}"

uv venv --python "${PYTHON_BIN}" --system-site-packages "${VENV_DIR}"
source "${VENV_DIR}/bin/activate"

PY_VER="$("${PYTHON_BIN}" - <<'PY'
import sys
print(f"{sys.version_info.major}.{sys.version_info.minor}")
PY
)"
SITE_PACKAGES="${VENV_DIR}/lib/python${PY_VER}/site-packages"
mkdir -p "${SITE_PACKAGES}"
if [[ -d "/opt/spack_store/view/lib/python${PY_VER}/site-packages" ]]; then
    echo "/opt/spack_store/view/lib/python${PY_VER}/site-packages" > "${SITE_PACKAGES}/spack-view.pth"
fi

"${PYTHON_BIN}" - <<PY > "${CONSTRAINTS_FILE}"
import importlib.metadata as md
import os
import re

spack_owned = set()
conf_path = "${SPACK_OWNED_CONF}"
if conf_path and os.path.isfile(conf_path):
    with open(conf_path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line and not line.startswith("#"):
                spack_owned.add(line.lower())

pins = {}
for dist in sorted(md.distributions(), key=lambda d: (d.metadata.get("Name", "").lower(), d.version)):
    name = dist.metadata.get("Name")
    if name and name.lower() in spack_owned:
        pins[name.lower()] = (name, re.sub(r"\+.*$", "", dist.version))

for _, (name, version) in sorted(pins.items()):
    print(f"{name}=={version}")
PY

UV_INSTALL_ARGS=(pip install --constraint "${CONSTRAINTS_FILE}")
if [[ -n "${NVIDIA_OVERRIDES}" ]]; then
    UV_INSTALL_ARGS+=(--override "${NVIDIA_OVERRIDES}")
fi
if [[ -n "${UV_EXTRA_OVERRIDES:-}" ]] && [[ -f "${UV_EXTRA_OVERRIDES}" ]]; then
    UV_INSTALL_ARGS+=(--override "${UV_EXTRA_OVERRIDES}")
fi
UV_INSTALL_ARGS+=("$@")

uv "${UV_INSTALL_ARGS[@]}"

echo "Installed packages in ${VENV_DIR}"
echo "Activate with: source ${VENV_DIR}/bin/activate"

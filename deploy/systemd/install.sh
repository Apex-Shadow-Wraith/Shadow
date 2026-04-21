#!/usr/bin/env bash
# Install Shadow's user-mode systemd units. Idempotent — re-run after
# editing any .service file in this directory to pick up changes.
set -euo pipefail

UNIT_DIR="${HOME}/.config/systemd/user"
SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

mkdir -p "$UNIT_DIR"

for unit in shadow-void.service; do
    install -m 0644 "$SRC_DIR/$unit" "$UNIT_DIR/$unit"
    echo "Installed: $UNIT_DIR/$unit"
done

systemctl --user daemon-reload

for unit in shadow-void.service; do
    systemctl --user enable --now "$unit"
    systemctl --user status "$unit" --no-pager --lines=5 || true
done

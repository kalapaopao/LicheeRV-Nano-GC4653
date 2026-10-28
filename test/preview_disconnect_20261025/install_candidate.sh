#!/bin/sh
# Install only this task's verified binary; never overwrite the board YAML.
set -eu
ROOT=/code/camera/modules/record80
STAGE=$ROOT/.preview_disconnect_20261025_232219
BACKUP=$ROOT/backup_preview_disconnect_20261025_232219
OLD=eb88aceb0275cdfa0714a28707ba1c82f5baaa6e63598fa1a49d4ea058e95b53
NEW=19edda678e7fb94f7e5cbe9a943949b936e6609d455aaa9451d65e8751671725
if [ -d /code/camera/run/lock ] || pidof camera_36record >/dev/null 2>&1; then
    echo CAMERA_BUSY; exit 2
fi
[ "$(sha256sum "$ROOT/camera_36record" | cut -d ' ' -f 1)" = "$OLD" ]
[ "$(sha256sum "$STAGE/camera_36record" | cut -d ' ' -f 1)" = "$NEW" ]
[ ! -e "$BACKUP" ]
mkdir "$BACKUP"
cp -p "$ROOT/camera_36record" "$BACKUP/camera_36record"
[ "$(sha256sum "$BACKUP/camera_36record" | cut -d ' ' -f 1)" = "$OLD" ]
sha256sum "$ROOT/config/record80.yaml" "$ROOT/run_board.sh" > "$BACKUP/unchanged.sha256"
cp "$STAGE/camera_36record" "$ROOT/camera_36record"
chmod 755 "$ROOT/camera_36record"
[ "$(sha256sum "$ROOT/camera_36record" | cut -d ' ' -f 1)" = "$NEW" ]
sha256sum -c "$BACKUP/unchanged.sha256"
echo INSTALL_PASS
echo BACKUP="$BACKUP"
sha256sum "$ROOT/camera_36record"

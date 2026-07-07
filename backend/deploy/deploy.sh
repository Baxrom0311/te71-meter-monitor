#!/bin/bash
# Deploy Meter Monitor backend + frontend.
# Usage: SERVER=root@1.2.3.4 bash backend/deploy/deploy.sh
set -e

: "${SERVER:?SERVER kerak, masalan: SERVER=root@1.2.3.4}"
REMOTE="${REMOTE:-/root/meter_backend}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND="${BACKEND:-$(cd "$SCRIPT_DIR/.." && pwd)}"
PROJECT_ROOT="${PROJECT_ROOT:-$(cd "$BACKEND/.." && pwd)}"
FRONTEND="${FRONTEND:-$PROJECT_ROOT/frontend}"
ENV_FILE="${ENV_FILE:-$SCRIPT_DIR/.env.production}"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "ENV_FILE topilmadi: $ENV_FILE"
  echo "Template: $SCRIPT_DIR/.env.production.example"
  exit 1
fi

if grep -Eq 'CHANGE_ME|change-in-prod|Admin1234' "$ENV_FILE"; then
  echo "Production env ichida placeholder yoki default secret bor: $ENV_FILE"
  exit 1
fi

echo "=== 1. Backend sync ==="
ssh "$SERVER" "mkdir -p $REMOTE/data $REMOTE/firmware $REMOTE/backups $REMOTE/frontend"
rsync -avz --exclude='__pycache__' --exclude='*.pyc' --exclude='.env' \
  --exclude='venv' --exclude='data' --exclude='backups' --exclude='firmware' \
  --exclude='tests' --exclude='deploy' \
  "$BACKEND/" "$SERVER:$REMOTE/"

echo "=== 2. Frontend sync ==="
rsync -avz \
  --exclude='*.map' \
  "$FRONTEND/" "$SERVER:$REMOTE/frontend/"

echo "=== 3. .env file ==="
scp "$ENV_FILE" "$SERVER:$REMOTE/.env"

echo "=== 4. systemd service ==="
scp "$BACKEND/deploy/meter-api.service" "$SERVER:/etc/systemd/system/meter-api.service"

echo "=== 5. Install/update Python deps ==="
ssh "$SERVER" "cd $REMOTE && test -x venv/bin/python || python3 -m venv venv && venv/bin/pip install -q -U pip && venv/bin/pip install -q -r requirements.txt"

echo "=== 6. Run migrations ==="
ssh "$SERVER" "cd $REMOTE && venv/bin/alembic upgrade head"

echo "=== 7. Restart service ==="
ssh "$SERVER" "systemctl daemon-reload && systemctl restart meter-api && sleep 2 && systemctl status meter-api --no-pager"

echo ""
echo "=== Done! ==="
echo "Frontend: http://${SERVER#*@}/"
echo "API docs: http://${SERVER#*@}/docs"

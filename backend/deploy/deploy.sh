#!/bin/bash
# Deploy Meter Monitor backend + frontend.
# Usage: SERVER=root@1.2.3.4 bash backend/deploy/deploy.sh
set -e

: "${SERVER:?SERVER kerak, masalan: SERVER=root@1.2.3.4}"
REMOTE="${REMOTE:-/root/meter_backend}"
SSH_KEY="${SSH_KEY:-$HOME/docean}"
SSH="ssh -i $SSH_KEY -o StrictHostKeyChecking=no"
SCP="scp -i $SSH_KEY -o StrictHostKeyChecking=no"
RPATH="export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND="${BACKEND:-$(cd "$SCRIPT_DIR/.." && pwd)}"
PROJECT_ROOT="${PROJECT_ROOT:-$(cd "$BACKEND/.." && pwd)}"
FRONTEND="${FRONTEND:-$PROJECT_ROOT/meter-frontend/dist}"
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
$SSH "$SERVER" "$RPATH && mkdir -p $REMOTE/data $REMOTE/firmware $REMOTE/backups $REMOTE/frontend"
COPYFILE_DISABLE=1 tar czf /tmp/meter_backend.tar.gz \
  --exclude='__pycache__' --exclude='*.pyc' --exclude='.env' \
  --exclude='venv' --exclude='data' --exclude='backups' --exclude='firmware' \
  --exclude='tests' --exclude='deploy' --exclude='._*' \
  -C "$BACKEND" .
$SCP /tmp/meter_backend.tar.gz "$SERVER:/tmp/meter_backend.tar.gz"
$SSH "$SERVER" "$RPATH && cd $REMOTE && tar xzf /tmp/meter_backend.tar.gz && rm /tmp/meter_backend.tar.gz"
rm /tmp/meter_backend.tar.gz

if [[ ! -f "$FRONTEND/index.html" ]]; then
  echo "Frontend build topilmadi: $FRONTEND/index.html"
  echo "Avval: cd $PROJECT_ROOT/meter-frontend && pnpm build"
  exit 1
fi

echo "=== 2. Frontend sync ==="
COPYFILE_DISABLE=1 tar czf /tmp/meter_frontend.tar.gz --exclude='*.map' --exclude='._*' -C "$FRONTEND" .
$SCP /tmp/meter_frontend.tar.gz "$SERVER:/tmp/meter_frontend.tar.gz"
$SSH "$SERVER" "$RPATH && mkdir -p $REMOTE/frontend && cd $REMOTE/frontend && tar xzf /tmp/meter_frontend.tar.gz && rm /tmp/meter_frontend.tar.gz"
rm /tmp/meter_frontend.tar.gz

echo "=== 3. .env file ==="
$SCP "$ENV_FILE" "$SERVER:$REMOTE/.env"

echo "=== 4. systemd service ==="
$SCP "$BACKEND/deploy/meter-api.service" "$SERVER:/etc/systemd/system/meter-api.service"

echo "=== 5. Install/update Python deps ==="
$SSH "$SERVER" "$RPATH && cd $REMOTE && test -x venv/bin/python || python3 -m venv venv && venv/bin/pip install -q -U pip && venv/bin/pip install -q -r requirements.txt"

echo "=== 6. Run migrations ==="
$SSH "$SERVER" "$RPATH && cd $REMOTE && venv/bin/alembic upgrade head"

echo "=== 7. Restart service ==="
$SSH "$SERVER" "$RPATH && systemctl daemon-reload && systemctl restart meter-api && sleep 2 && systemctl status meter-api --no-pager"

echo ""
echo "=== Done! ==="
echo "Frontend: https://ss.boos.uz/"
echo "API docs: https://ss.boos.uz/docs"

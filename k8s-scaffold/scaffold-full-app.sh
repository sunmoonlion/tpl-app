#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TPL_DIR="$SCRIPT_DIR/tpl"

if [[ $# -lt 1 ]]; then
    echo "用法: $0 <app-name> [--output-dir DIR] [--namespace NAMESPACE]" >&2
    exit 1
fi

APP_NAME="$1"
shift
OUTPUT_DIR="."
NAMESPACE="app-platform-dev"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --output-dir) OUTPUT_DIR="$2"; shift 2 ;;
        --namespace) NAMESPACE="$2"; shift 2 ;;
        *) echo "未知参数: $1" >&2; exit 1 ;;
    esac
done

APP_UPPER="$(echo "$APP_NAME" | tr '-' '_' | tr '[:lower:]' '[:upper:]')"
APP_TITLE="$(tr '[:lower:]' '[:upper:]' <<< "${APP_NAME:0:1}")${APP_NAME:1}"
APP_DIR="$OUTPUT_DIR/${APP_NAME}-app"
mkdir -p "$APP_DIR"

"$SCRIPT_DIR/scaffold.sh" "${APP_NAME}-admin-backend" 8000 \
    --type backend --namespace "$NAMESPACE" \
    --output-dir "$APP_DIR/${APP_NAME}-admin-backend"
"$SCRIPT_DIR/scaffold.sh" "${APP_NAME}-admin-frontend" 80 \
    --type static-frontend --namespace "$NAMESPACE" \
    --output-dir "$APP_DIR/${APP_NAME}-admin-frontend"
"$SCRIPT_DIR/scaffold.sh" "${APP_NAME}-web-backend" 3000 \
    --type backend --namespace "$NAMESPACE" \
    --output-dir "$APP_DIR/${APP_NAME}-web-backend"
"$SCRIPT_DIR/scaffold.sh" "${APP_NAME}-web-frontend" 3000 \
    --type node-frontend --namespace "$NAMESPACE" \
    --output-dir "$APP_DIR/${APP_NAME}-web-frontend"
"$SCRIPT_DIR/scaffold-workers.sh" "$APP_NAME" \
    --output-dir "$APP_DIR"

ALL_DIR="$APP_DIR/deploy-${APP_NAME}-app-all"
mkdir -p "$ALL_DIR"
sed \
    -e "s|__APP_UPPER__|$APP_UPPER|g" \
    -e "s|__APP_TITLE__|$APP_TITLE|g" \
    -e "s|__APP__|$APP_NAME|g" \
    "$TPL_DIR/deploy-business-app-all.conf.tpl" \
    > "$ALL_DIR/deploy-${APP_NAME}-app-all.conf"
sed \
    -e "s|__APP_UPPER__|$APP_UPPER|g" \
    -e "s|__APP_TITLE__|$APP_TITLE|g" \
    -e "s|__APP__|$APP_NAME|g" \
    "$TPL_DIR/deploy-business-app-all.sh.tpl" \
    > "$ALL_DIR/deploy-${APP_NAME}-app-all.sh"
chmod +x "$ALL_DIR/deploy-${APP_NAME}-app-all.sh"

echo "完整 K8s App 目录已生成: $APP_DIR"

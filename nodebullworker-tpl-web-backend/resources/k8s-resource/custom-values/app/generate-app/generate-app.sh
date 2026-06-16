#!/bin/bash
# nodebullworker-tpl-web-backend Deployment YAML 生成脚本

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="$SCRIPT_DIR/generate-app.conf"
# 从 generate-app/ -> app/ -> custom-values/ -> k8s-resource/
K8S_RESOURCE_DIR="$(cd "$SCRIPT_DIR/../../.." && pwd)"
# 从 generate-app/ -> app/ -> custom-values/ -> k8s-resource/ -> resources/ -> nodebullworker-tpl-web-backend/
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../../../.." && pwd)"
OUTPUT_DIR="$SCRIPT_DIR"

MAIN_DEPLOY_CONFIG="$PROJECT_ROOT/deploy-nodebullworker-tpl-web-backend/app/deploy-app/deploy-nodebullworker-tpl-web-backend.conf"
if [ -f "$MAIN_DEPLOY_CONFIG" ]; then
    _temp_namespace=$(source "$MAIN_DEPLOY_CONFIG" 2>/dev/null && echo "${NODEBULLWORKER_TPL_WEB_BACKEND_NAMESPACE:-}")
    _temp_environment=$(source "$MAIN_DEPLOY_CONFIG" 2>/dev/null && echo "${ENVIRONMENT:-}")
    [ -n "$_temp_namespace" ] && [ -z "${NAMESPACE:-}" ] && export NAMESPACE="$_temp_namespace"
    [ -n "$_temp_environment" ] && [ -z "${ENVIRONMENT:-}" ] && export ENVIRONMENT="$_temp_environment"
    unset _temp_namespace _temp_environment
fi

log_info()    { echo -e "\033[0;34m[INFO]\033[0m $*"; }
log_success() { echo -e "\033[0;32m[SUCCESS]\033[0m $*"; }
log_error()   { echo -e "\033[0;31m[ERROR]\033[0m $*" >&2; }
log_warn()    { echo -e "\033[1;33m[WARN]\033[0m $*"; }

if [ ! -f "$CONFIG_FILE" ]; then
    log_error "配置文件不存在: $CONFIG_FILE"; exit 1
fi
source "$CONFIG_FILE"

if [ "${ENABLED:-true}" != "true" ]; then
    log_info "跳过资源生成: app (已禁用)"; exit 0
fi

export NAMESPACE="${NAMESPACE:-}"
export ENVIRONMENT="${ENVIRONMENT:-}"
export ENV="${ENV:-}"

export NODEBULLWORKER_TPL_WEB_BACKEND_IMAGE_REGISTRY="${NODEBULLWORKER_TPL_WEB_BACKEND_IMAGE_REGISTRY:-}"
export NODEBULLWORKER_TPL_WEB_BACKEND_IMAGE_PROJECT="${NODEBULLWORKER_TPL_WEB_BACKEND_IMAGE_PROJECT:-}"
export NODEBULLWORKER_TPL_WEB_BACKEND_IMAGE="${NODEBULLWORKER_TPL_WEB_BACKEND_IMAGE:-}"
export NODEBULLWORKER_TPL_WEB_BACKEND_TAG="${NODEBULLWORKER_TPL_WEB_BACKEND_TAG:-}"
export NODEBULLWORKER_TPL_WEB_BACKEND_FULL_IMAGE_NAME="${NODEBULLWORKER_TPL_WEB_BACKEND_IMAGE_REGISTRY}/${NODEBULLWORKER_TPL_WEB_BACKEND_IMAGE_PROJECT}/${NODEBULLWORKER_TPL_WEB_BACKEND_IMAGE}:${NODEBULLWORKER_TPL_WEB_BACKEND_TAG}"
export IMAGE_PULL_POLICY="${IMAGE_PULL_POLICY:-}"
export NODEBULLWORKER_TPL_WEB_BACKEND_IMAGE_PULL_SECRET_NAME="${NODEBULLWORKER_TPL_WEB_BACKEND_IMAGE_PULL_SECRET_NAME:-}"
export NODEBULLWORKER_TPL_WEB_BACKEND_SECRET_NAME="${NODEBULLWORKER_TPL_WEB_BACKEND_SECRET_NAME:-}"
export NODEBULLWORKER_TPL_WEB_BACKEND_CONFIGMAP_NAME="${NODEBULLWORKER_TPL_WEB_BACKEND_CONFIGMAP_NAME:-}"
export NODEBULLWORKER_TPL_WEB_BACKEND_QUEUE_REDIS_SECRET_NAME="${NODEBULLWORKER_TPL_WEB_BACKEND_QUEUE_REDIS_SECRET_NAME:-}"
export TPL_WEB_BACKEND_SECRET_NAME="${TPL_WEB_BACKEND_SECRET_NAME:-}"
export TPL_WEB_BACKEND_CONFIGMAP_NAME="${TPL_WEB_BACKEND_CONFIGMAP_NAME:-}"
export PVC_NAME="${PVC_NAME:-}"
export PVC_MOUNT_PATH="${PVC_MOUNT_PATH:-}"
export PVC_SUB_PATH="${PVC_SUB_PATH:-}"

validate_yaml() {
    local yaml_file="$1"
    if command -v kubectl &> /dev/null; then
        if kubectl apply --dry-run=client -f "$yaml_file" &> /dev/null; then
            log_success "YAML 验证通过: $(basename "$yaml_file")"
        else
            log_error "YAML 验证失败: $(basename "$yaml_file")"
            kubectl apply --dry-run=client -f "$yaml_file" 2>&1 | head -20
            return 1
        fi
    else
        log_warn "kubectl 未安装，跳过 YAML 验证"
    fi
}

main() {
    log_info "开始生成 nodebullworker-tpl-web-backend YAML 文件..."
    log_info "输出目录: $OUTPUT_DIR"

    local full_template_path
    if [[ "$TEMPLATE_FILE" = /* ]]; then
        full_template_path="$TEMPLATE_FILE"
    else
        full_template_path="$K8S_RESOURCE_DIR/$TEMPLATE_FILE"
    fi
    local full_output_path="$OUTPUT_DIR/$OUTPUT_FILE"

    if [ ! -f "$full_template_path" ]; then
        log_error "模板文件不存在: $full_template_path"; exit 1
    fi

    log_info "生成 app: $OUTPUT_FILE"
    sed -e 's/\${\([^:}]*\):-[^}]*}/\${\1}/g' "$full_template_path" | envsubst > "$full_output_path"
    sed -i \
        -e 's|__CONTAINER_NODE_ENV_DEFAULT__|\${NODE_ENV:-production}|g' \
        -e 's|__CONTAINER_QUEUE_ON_DEFAULT__|\${QUEUE_ON:-true}|g' \
        "$full_output_path"
    validate_yaml "$full_output_path"
    log_success "✅ app 生成完成: $OUTPUT_FILE"
}

main "$@"

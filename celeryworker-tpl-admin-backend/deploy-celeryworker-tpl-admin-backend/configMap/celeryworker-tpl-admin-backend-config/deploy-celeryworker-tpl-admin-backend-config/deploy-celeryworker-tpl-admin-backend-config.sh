#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="$SCRIPT_DIR/deploy-celeryworker-tpl-admin-backend-config.conf"
# 从 deploy-celeryworker-tpl-admin-backend-config/ -> celeryworker-tpl-admin-backend-config/ -> configMap/ -> deploy-celeryworker-tpl-admin-backend/ -> celeryworker-tpl-admin-backend/
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../../.." && pwd)"
K8S_RESOURCE_DIR="$PROJECT_ROOT/resources/k8s-resource"
CONFIG_YAML="$K8S_RESOURCE_DIR/custom-values/configMap/celeryworker-tpl-admin-backend-config/generate-celeryworker-tpl-admin-backend-config/celeryworker-tpl-admin-backend-config-generated.yaml"

log_info()    { echo -e "[INFO] $*"; }
log_success() { echo -e "\033[32m[SUCCESS]\033[0m $*"; }
log_error()   { echo -e "\033[31m[ERROR]\033[0m $*" 1>&2; }
log_warn()    { echo -e "\033[33m[WARN]\033[0m $*"; }

[[ -f "$CONFIG_FILE" ]] && source "$CONFIG_FILE" || log_warn "未找到配置文件: $CONFIG_FILE"

main() {
    local action="${1:-deploy}"
    local project_id="${2:-${PROJECT_ID:-}}"
    local namespace="${3:-${NAMESPACE:-}}"
    local environment="${4:-${ENVIRONMENT:-}}"

    export PROJECT_ID="$project_id" NAMESPACE="$namespace" ENVIRONMENT="$environment" ENV="${ENV:-dev}"

    local generate_script="$K8S_RESOURCE_DIR/custom-values/configMap/celeryworker-tpl-admin-backend-config/generate-celeryworker-tpl-admin-backend-config/generate-celeryworker-tpl-admin-backend-config.sh"
    if [ -f "$generate_script" ]; then
        bash "$generate_script" || { log_error "ConfigMap YAML 生成失败"; exit 1; }
        log_success "ConfigMap YAML 生成成功"
    else
        log_error "生成脚本不存在: $generate_script"; exit 1
    fi

    case "$action" in
        deploy)
            kubectl apply -f "$CONFIG_YAML" -n "$NAMESPACE"
            log_success "celeryworker-tpl-admin-backend ConfigMap 部署完成"
            ;;
        uninstall)
            kubectl delete -f "$CONFIG_YAML" -n "$NAMESPACE" --ignore-not-found
            log_success "celeryworker-tpl-admin-backend ConfigMap 卸载完成"
            ;;
        status)
            kubectl get configmap "celeryworker-tpl-admin-backend-config" -n "$NAMESPACE" 2>/dev/null \
                || log_warn "ConfigMap 不存在: celeryworker-tpl-admin-backend-config"
            ;;
        generate)
            log_success "仅生成 YAML，未部署"
            ;;
        *)
            log_error "无效操作: $action"
            echo "用法: $0 <deploy|uninstall|status|generate> [project_id] [namespace] [environment]"
            exit 1
            ;;
    esac
}

main "$@"

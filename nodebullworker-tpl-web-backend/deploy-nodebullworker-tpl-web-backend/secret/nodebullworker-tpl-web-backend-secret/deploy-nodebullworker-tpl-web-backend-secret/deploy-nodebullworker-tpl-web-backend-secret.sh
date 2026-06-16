#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="$SCRIPT_DIR/deploy-nodebullworker-tpl-web-backend-secret.conf"
# 从 deploy-nodebullworker-tpl-web-backend-secret/ -> nodebullworker-tpl-web-backend-secret/ -> secret/ -> deploy-nodebullworker-tpl-web-backend/ -> nodebullworker-tpl-web-backend/
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../../.." && pwd)"
K8S_RESOURCE_DIR="$PROJECT_ROOT/resources/k8s-resource"
SECRET_YAML="$K8S_RESOURCE_DIR/custom-values/secret/nodebullworker-tpl-web-backend-secret/generate-nodebullworker-tpl-web-backend-secret/nodebullworker-tpl-web-backend-secret-generated.yaml"

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

    local generate_script="$K8S_RESOURCE_DIR/custom-values/secret/nodebullworker-tpl-web-backend-secret/generate-nodebullworker-tpl-web-backend-secret/generate-nodebullworker-tpl-web-backend-secret.sh"
    if [ -f "$generate_script" ]; then
        bash "$generate_script" || { log_error "Secret YAML 生成失败"; exit 1; }
        log_success "Secret YAML 生成成功"
    else
        log_error "生成脚本不存在: $generate_script"; exit 1
    fi

    case "$action" in
        deploy)
            kubectl apply -f "$SECRET_YAML" -n "$NAMESPACE"
            log_success "nodebullworker-tpl-web-backend Secret 部署完成"
            ;;
        uninstall)
            kubectl delete -f "$SECRET_YAML" -n "$NAMESPACE" --ignore-not-found
            log_success "nodebullworker-tpl-web-backend Secret 卸载完成"
            ;;
        status)
            kubectl get secret "nodebullworker-tpl-web-backend-secret" -n "$NAMESPACE" 2>/dev/null \
                || log_warn "Secret 不存在: nodebullworker-tpl-web-backend-secret"
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

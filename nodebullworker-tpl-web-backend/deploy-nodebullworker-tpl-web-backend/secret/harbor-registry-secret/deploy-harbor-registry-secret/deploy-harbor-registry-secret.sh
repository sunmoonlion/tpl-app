#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="$SCRIPT_DIR/deploy-harbor-registry-secret.conf"
# 从 deploy-harbor-registry-secret/ -> harbor-registry-secret/ -> secret/ -> deploy-nodebullworker-tpl-web-backend/ -> nodebullworker-tpl-web-backend/
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../../.." && pwd)"

find_k8s_root_dir() {
    local search_dir="$1"
    while [[ -n "$search_dir" && "$search_dir" != "/" ]]; do
        if [[ -f "$search_dir/utils/cluster-config-mapping.sh" ]]; then
            echo "$search_dir"
            return 0
        fi
        search_dir="$(dirname "$search_dir")"
    done
    return 1
}
K8S_ROOT_DIR="$(find_k8s_root_dir "$PROJECT_ROOT" || true)"
if [[ -n "${K8S_ROOT_DIR:-}" ]]; then
    source "$K8S_ROOT_DIR/utils/cluster-config-mapping.sh"
fi

K8S_RESOURCE_DIR="$PROJECT_ROOT/resources/k8s-resource"
HARBOR_YAML="$K8S_RESOURCE_DIR/custom-values/secret/harbor-registry-secret/generate-harbor-registry-secret/harbor-registry-secret-generated.yaml"

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

    if declare -F apply_cluster_config_mapping >/dev/null; then
        apply_cluster_config_mapping
    fi

    if declare -F get_cluster_harbor_registry >/dev/null; then
        export DOCKER_SERVER="${DOCKER_SERVER:-$(get_cluster_harbor_registry)}"
    else
        export DOCKER_SERVER="${DOCKER_SERVER:-harbor.sunmoonai.com:30443}"
    fi

    export PROJECT_ID="$project_id" NAMESPACE="$namespace" ENVIRONMENT="$environment" ENV="${ENV:-dev}"

    if [[ "$action" == "deploy" ]] && kubectl get secret "harbor-registry-secret" -n "$NAMESPACE" >/dev/null 2>&1; then
        log_success "复用命名空间现有 Harbor Registry Secret"
        return 0
    fi

    local generate_script="$K8S_RESOURCE_DIR/custom-values/secret/harbor-registry-secret/generate-harbor-registry-secret/generate-harbor-registry-secret.sh"
    if [ -f "$generate_script" ]; then
        bash "$generate_script" || { log_error "Harbor Secret YAML 生成失败"; exit 1; }
        log_success "Harbor Secret YAML 生成成功"
    else
        log_error "生成脚本不存在: $generate_script"; exit 1
    fi

    case "$action" in
        deploy)
            kubectl apply -f "$HARBOR_YAML" -n "$NAMESPACE"
            log_success "Harbor Registry Secret 部署完成"
            ;;
        uninstall)
            kubectl delete -f "$HARBOR_YAML" -n "$NAMESPACE" --ignore-not-found
            log_success "Harbor Registry Secret 卸载完成"
            ;;
        status)
            kubectl get secret "harbor-registry-secret" -n "$NAMESPACE" 2>/dev/null \
                || log_warn "Secret 不存在: harbor-registry-secret"
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

#!/usr/bin/env bash
set -euo pipefail

THIS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUSINESS_APP_ROOT="$(dirname "$THIS_DIR")"
BUSINESS_APP_NAME="$(basename "$BUSINESS_APP_ROOT")"

K8S_ROOT_DIR="${SUNMOONAI_K8S_ROOT:-}"
search_dir="$THIS_DIR"
while [[ -z "$K8S_ROOT_DIR" && "$search_dir" != "/" ]]; do
    if [[ -f "$search_dir/utils/cluster-arg-parser.sh" ]]; then
        K8S_ROOT_DIR="$search_dir"
        break
    fi
    search_dir="$(dirname "$search_dir")"
done
if [[ -z "$K8S_ROOT_DIR" || ! -f "$K8S_ROOT_DIR/utils/cluster-arg-parser.sh" ]]; then
    echo "[ERROR] 无法定位 k8s 根目录" >&2
    exit 1
fi

source "$K8S_ROOT_DIR/utils/cluster-arg-parser.sh"

log_info() { echo "ℹ️  $*"; }
log_success() { echo "✅ $*"; }
log_error() { echo "❌ $*" >&2; }

ORIGINAL_ARGS=("$@")
if [[ $# -gt 0 ]]; then
    unified_parse_cluster_arg "$@"
    ORIGINAL_ARGS=("${PARSED_ARGS[@]}")
fi

CONFIG_FILE="$THIS_DIR/deploy-${BUSINESS_APP_NAME}-all.conf"
[[ -f "$CONFIG_FILE" ]] || {
    log_error "缺少配置文件: $CONFIG_FILE"
    exit 1
}
source "$CONFIG_FILE"
if [[ -f "$K8S_ROOT_DIR/utils/cluster-config-mapping.sh" ]]; then
    source "$K8S_ROOT_DIR/utils/cluster-config-mapping.sh"
    apply_cluster_config_mapping
fi

VAR_PREFIX="$(echo "$BUSINESS_APP_NAME" | tr '[:lower:]-' '[:upper:]_')"
eval "DEFAULT_PROJECT_ID=\${${VAR_PREFIX}_PROJECT_ID:-sunmoonai}"
eval "DEFAULT_NAMESPACE=\${${VAR_PREFIX}_NAMESPACE:-app-platform-dev}"
eval "APP_IMAGE_TAG=\${${VAR_PREFIX}_IMAGE_TAG:-1.0.0}"
DEFAULT_ENVIRONMENT="${ENVIRONMENT:-development}"

APP_VAR_PREFIX="$(echo "${BUSINESS_APP_NAME%-app}" | tr '[:lower:]-' '[:upper:]_')"
for component in ADMIN_BACKEND ADMIN_FRONTEND WEB_BACKEND WEB_FRONTEND; do
    export "${APP_VAR_PREFIX}_${component}_TAG=${APP_IMAGE_TAG}"
done
export "CELERYWORKER_${APP_VAR_PREFIX}_ADMIN_BACKEND_TAG=${APP_IMAGE_TAG}"
export "NODEBULLWORKER_${APP_VAR_PREFIX}_WEB_BACKEND_TAG=${APP_IMAGE_TAG}"

call_subscript() {
    local script_path="$1"
    shift
    if [[ -n "${CLUSTER:-}" ]]; then
        "$script_path" --cluster "$CLUSTER" "$@"
    else
        "$script_path" "$@"
    fi
}

run_bootstrap() {
    local label="$1"
    local script_path="$2"
    local action="$3"
    local cluster="${CLUSTER:-KIND}"

    [[ -x "$script_path" ]] || {
        log_error "${label} 脚本不存在或不可执行: $script_path"
        return 1
    }
    log_info "${label}: ${action} (cluster=${cluster})"
    CLUSTER="$cluster" ELASTICSEARCH_CLUSTER="$cluster" OBJECT_STORAGE_CLUSTER="$cluster" \
        "$script_path" "$action"
}

run_backend_resources() {
    local backend="$1"
    local action="$2"
    local source_root="$3"
    local storage_enabled_var="${backend//-/_}_storage_access_enabled"
    local search_enabled_var="${backend//-/_}_search_access_enabled"
    local database_enabled_var="${backend//-/_}_database_access_enabled"
    local database_enabled storage_enabled search_enabled
    eval "database_enabled=\${${database_enabled_var}:-false}"
    eval "storage_enabled=\${${storage_enabled_var}:-false}"
    eval "search_enabled=\${${search_enabled_var}:-false}"

    if [[ "$database_enabled" == "true" ]]; then
        run_bootstrap "$backend Database" \
            "$source_root/$backend/db-access-bootstrap/db-access-bootstrap.sh" \
            "$action"
    fi
    if [[ "$storage_enabled" == "true" ]]; then
        run_bootstrap "$backend S3" \
            "$source_root/$backend/storage-access-bootstrap/storage-access-bootstrap.sh" \
            "$action"
    fi
    if [[ "$search_enabled" == "true" ]]; then
        run_bootstrap "$backend Elasticsearch" \
            "$source_root/$backend/search-access-bootstrap/search-access-bootstrap.sh" \
            "$action"
    fi
}

run_domain_resources() {
    local action="$1"
    local dry_run="${2:-false}"
    local source_var="${VAR_PREFIX}_SOURCE_ROOT"
    local source_root
    eval "source_root=\${${source_var}:-${HOME}/${BUSINESS_APP_NAME}}"
    local bootstrap_action

    case "$action" in
        deploy)
            bootstrap_action="provision"
            [[ "$dry_run" == "true" ]] && bootstrap_action="validate"
            ;;
        provision-resources) bootstrap_action="provision" ;;
        validate-resources) bootstrap_action="validate" ;;
        status|resource-status) bootstrap_action="status" ;;
        uninstall|logs) return 0 ;;
        *) log_error "不支持的资源操作: $action"; return 1 ;;
    esac

    local app_prefix="${BUSINESS_APP_NAME%-app}"
    run_backend_resources "${app_prefix}-admin-backend" "$bootstrap_action" "$source_root"
    run_backend_resources "${app_prefix}-web-backend" "$bootstrap_action" "$source_root"
}

find_component_script() {
    local component_dir="$1"
    local matches=()
    shopt -s nullglob
    matches=("$component_dir"/deploy-*/app/deploy-app/deploy-*.sh)
    [[ ${#matches[@]} -gt 0 ]] || matches=("$component_dir"/deploy-*/deploy-*.sh)
    shopt -u nullglob
    [[ ${#matches[@]} -gt 0 ]] || return 1
    printf '%s\n' "${matches[0]}"
}

collect_components() {
    local component_dir component_name var_base enabled priority script_path
    for component_dir in "$BUSINESS_APP_ROOT"/*; do
        [[ -d "$component_dir" ]] || continue
        component_name="$(basename "$component_dir")"
        [[ "$component_name" =~ ^deploy-.*-all$ ]] && continue
        var_base="${component_name//-/_}"
        eval "enabled=\${${var_base}_enabled:-false}"
        eval "priority=\${${var_base}_priority:-100}"
        if script_path="$(find_component_script "$component_dir")"; then
            printf '%s:%s:%s:%s\n' "$priority" "$component_name" "$enabled" "$script_path"
        elif [[ "$enabled" == "true" ]]; then
            printf '%s:%s:%s:\n' "$priority" "$component_name" "$enabled"
        fi
    done
}

run_components() {
    local action="$1" project_id="$2" namespace="$3" environment="$4" dry_run="$5"
    local sort_flag="-nr"
    [[ "$action" == "uninstall" ]] && sort_flag="-n"
    local component_info priority component_name enabled script_path

    while IFS= read -r component_info; do
        [[ -n "$component_info" ]] || continue
        IFS=':' read -r priority component_name enabled script_path <<< "$component_info"
        [[ "$enabled" == "true" ]] || continue
        [[ -f "$script_path" ]] || {
            log_error "组件部署脚本不存在: $component_name"
            return 1
        }
        call_subscript "$script_path" "$action" \
            "$project_id" "$namespace" "$environment" "$dry_run"
    done < <(collect_components | sort "$sort_flag" -t: -k1,1)
}

run_business_app() {
    local action="$1"
    local project_id="${2:-$DEFAULT_PROJECT_ID}"
    local namespace="${3:-$DEFAULT_NAMESPACE}"
    local environment="${4:-$DEFAULT_ENVIRONMENT}"
    local dry_run="${5:-false}"

    run_domain_resources "$action" "$dry_run"
    case "$action" in
        provision-resources|validate-resources|resource-status)
            log_success "${BUSINESS_APP_NAME} $action 完成"
            return 0
            ;;
    esac
    run_components "$action" "$project_id" "$namespace" "$environment" "$dry_run"
    log_success "${BUSINESS_APP_NAME} $action 完成"
}

main() {
    set -- "${ORIGINAL_ARGS[@]}"
    local action="${1:-deploy}"
    case "$action" in
        deploy|uninstall|status|logs|provision-resources|validate-resources|resource-status)
            shift || true
            ;;
        *)
            log_error "未知操作: $action"
            return 1
            ;;
    esac
    run_business_app "$action" \
        "${1:-$DEFAULT_PROJECT_ID}" \
        "${2:-$DEFAULT_NAMESPACE}" \
        "${3:-$DEFAULT_ENVIRONMENT}" \
        "${4:-false}"
}

main "$@"

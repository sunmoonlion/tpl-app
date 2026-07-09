#!/bin/bash

# celeryworker-tpl-admin-backend 部署脚本
# 用法: ./deploy-celeryworker-tpl-admin-backend.sh <deploy|uninstall|status> [project_id] [namespace] [environment]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# 从 app/deploy-app/ 向上 2 级到达 deploy-celeryworker-tpl-admin-backend/
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
# 向上 1 级到达应用根目录
APP_ROOT="$(cd "$PROJECT_ROOT/.." && pwd)"

CELERYWORKER_TPL_ADMIN_BACKEND_SCRIPT_DIR="$SCRIPT_DIR"

find_k8s_root_dir() {
    local search_dir="$1"
    while [[ -n "$search_dir" && "$search_dir" != "/" ]]; do
        if [[ -f "$search_dir/utils/cluster-arg-parser.sh" ]]; then
            echo "$search_dir"
            return 0
        fi
        search_dir="$(dirname "$search_dir")"
    done
    return 1
}
K8S_ROOT_DIR="$(find_k8s_root_dir "$APP_ROOT")"
if [[ -z "${K8S_ROOT_DIR:-}" ]]; then
    echo "[ERROR] 无法定位 k8s 根目录（未找到 utils/cluster-arg-parser.sh），APP_ROOT=$APP_ROOT" 1>&2
    exit 1
fi

source "$K8S_ROOT_DIR/utils/unified-deployment-template.sh"

SCRIPT_DIR="$CELERYWORKER_TPL_ADMIN_BACKEND_SCRIPT_DIR"

ORIGINAL_ARGS=("$@")
if [[ $# -gt 0 ]]; then
    unified_parse_cluster_arg "$@"
    ORIGINAL_ARGS=("${PARSED_ARGS[@]}")
fi

CELERYWORKER_TPL_ADMIN_BACKEND_CONFIG_FILE="$SCRIPT_DIR/deploy-celeryworker-tpl-admin-backend.conf"
if [[ -f "$CELERYWORKER_TPL_ADMIN_BACKEND_CONFIG_FILE" ]]; then
    source "$CELERYWORKER_TPL_ADMIN_BACKEND_CONFIG_FILE"

    if [[ -f "$K8S_ROOT_DIR/utils/cluster-config-mapping.sh" ]]; then
        source "$K8S_ROOT_DIR/utils/cluster-config-mapping.sh"
        apply_cluster_config_mapping
    fi

    log_info "已加载 celeryworker-tpl-admin-backend 配置文件: $CELERYWORKER_TPL_ADMIN_BACKEND_CONFIG_FILE"
else
    log_warn "未找到 celeryworker-tpl-admin-backend 配置文件: $CELERYWORKER_TPL_ADMIN_BACKEND_CONFIG_FILE，使用默认配置"
fi

DEFAULT_PROJECT_ID="${CELERYWORKER_TPL_ADMIN_BACKEND_PROJECT_ID:-}"
DEFAULT_NAMESPACE="${CELERYWORKER_TPL_ADMIN_BACKEND_NAMESPACE:-}"
DEFAULT_ENVIRONMENT="${ENVIRONMENT:-}"

RESOURCES_DIR="$APP_ROOT/resources"
K8S_RESOURCE_DIR="${RESOURCES_DIR}/k8s-resource"
CELERYWORKER_TPL_ADMIN_BACKEND_YAML="${K8S_RESOURCE_DIR}/custom-values/app/generate-app/celeryworker-tpl-admin-backend-generated.yaml"
CELERYWORKER_TPL_ADMIN_BACKEND_PVC_YAML="${K8S_RESOURCE_DIR}/custom-values/pvc/celeryworker-tpl-admin-backend-pvc/generate-celeryworker-tpl-admin-backend-pvc/celeryworker-tpl-admin-backend-pvc-generated.yaml"

check_kubectl() {
    if ! command -v kubectl &> /dev/null; then
        log_error "kubectl 未安装或不在 PATH 中"
        exit 1
    fi
}

check_namespace() {
    local namespace="$1"
    if ! kubectl get nodes >/dev/null 2>&1; then
        if ! setup_kubectl_environment; then
            log_error "❌ 无法建立 Kubernetes 连接"
            return 1
        fi
    fi
    local _ns_err
    _ns_err=$(kubectl get namespace "$namespace" 2>&1)
    if [[ $? -eq 0 ]]; then
        log_success "✅ 命名空间 $namespace 已存在"
        return 0
    elif echo "$_ns_err" | grep -qiE "not.?found|NotFound"; then
        log_error "❌ 命名空间 $namespace 不存在！请先创建："
        echo "  kubectl create namespace $namespace"
        return 1
    else
        log_warn "kubectl 连接失败，尝试重连（${_ns_err%%$'\n'*}）"
        if command -v setup_kubectl_environment >/dev/null 2>&1 && setup_kubectl_environment >/dev/null 2>&1; then
            if kubectl get namespace "$namespace" >/dev/null 2>&1; then
                log_success "✅ 重连后命名空间 $namespace 已存在"
                return 0
            fi
        fi
        log_error "❌ kubectl 连接失败，请检查 KUBECONFIG"
        return 1
    fi
}

auto_generate_yaml() {
    local yaml_file="$1"
    log_info "重新生成 YAML 文件..."

    local generate_script=""
    if [[ "$yaml_file" == *"celeryworker-tpl-admin-backend-pvc-generated.yaml" ]]; then
        generate_script="${K8S_RESOURCE_DIR}/custom-values/pvc/celeryworker-tpl-admin-backend-pvc/generate-celeryworker-tpl-admin-backend-pvc/generate-celeryworker-tpl-admin-backend-pvc.sh"
    else
        generate_script="${K8S_RESOURCE_DIR}/custom-values/app/generate-app/generate-app.sh"
    fi

    if [ -f "$generate_script" ]; then
        export NAMESPACE="${CELERYWORKER_TPL_ADMIN_BACKEND_NAMESPACE:-}"
        export ENVIRONMENT="${ENVIRONMENT:-development}"
        export ENV="${ENV:-dev}"
        export PROJECT_ID="${CELERYWORKER_TPL_ADMIN_BACKEND_PROJECT_ID:-}"

        if bash "$generate_script"; then
            log_success "YAML 文件生成成功"
        else
            log_error "YAML 文件生成失败"
            return 1
        fi
    else
        log_error "生成脚本不存在: $generate_script"
        return 1
    fi
    return 0
}

scan_and_deploy_components() {
    local component_type="$1"
    local project_id="$2"
    local namespace="$3"
    local environment="$4"
    local dry_run="${5:-}"
    local base_dir="$PROJECT_ROOT/$component_type"
    local components=()

    log_info "扫描 $component_type/ 目录..."

    if [[ ! -d "$base_dir" ]]; then
        log_warn "目录不存在: $base_dir，跳过 $component_type"
        return 0
    fi

    for subdir in "$base_dir"/*/; do
        [[ ! -d "$subdir" ]] && continue
        local dirname
        dirname=$(basename "$subdir")
        [[ "$dirname" =~ ^deploy-.*-all$ ]] && continue

        local deploy_dir script_file conf_file
        if [[ "$component_type" == "ingress" ]]; then
            deploy_dir="$subdir/deploy-ingress"
            script_file="$deploy_dir/deploy-ingress.sh"
            conf_file="$deploy_dir/deploy-ingress.conf"
        else
            deploy_dir="$subdir/deploy-${dirname}"
            script_file="$deploy_dir/deploy-${dirname}.sh"
            conf_file="$deploy_dir/deploy-${dirname}.conf"
        fi

        [[ ! -d "$deploy_dir" ]] && { log_warn "未找到部署目录: $deploy_dir，跳过 $dirname"; continue; }
        [[ ! -f "$script_file" ]] && { log_warn "部署脚本不存在: $script_file，跳过 $dirname"; continue; }

        local var_base enabled priority description
        var_base=$(echo "$dirname" | tr '-' '_')
        enabled="true"
        priority="100"
        description="$dirname"

        if [[ -f "$conf_file" ]]; then
            source "$conf_file" 2>/dev/null || true
            eval "enabled=\${${var_base}_enabled:-true}"
            eval "priority=\${${var_base}_priority:-100}"
            eval "description=\${${var_base}_description:-$dirname}"
        fi

        components+=("$dirname:$enabled:$priority:$description:$script_file")
    done

    if [[ ${#components[@]} -eq 0 ]]; then
        log_info "未找到 $component_type 组件，跳过"
        return 0
    fi

    IFS=$'\n' sorted_components=($(printf '%s\n' "${components[@]}" | sort -t: -k3 -nr))
    unset IFS

    log_info "📋 $component_type 部署顺序："
    for c in "${sorted_components[@]}"; do
        IFS=':' read -r name enabled priority desc script <<< "$c"
        if [[ "$enabled" == "true" ]]; then
            log_info "  🚀 $priority - $desc"
        else
            log_info "  ⏭️  $priority - $desc (已禁用)"
        fi
    done

    for c in "${sorted_components[@]}"; do
        IFS=':' read -r name enabled priority desc script <<< "$c"
        if [[ "$enabled" == "true" ]]; then
            log_info "🚀 部署 $desc..."
            if DISABLE_AUTO_CLEANUP=true bash "$script" deploy "$project_id" "$namespace" "$environment" "$dry_run"; then
                log_success "✅ $desc 部署成功"
            else
                log_error "❌ $desc 部署失败"
                return 1
            fi
        else
            log_info "⏭️  跳过 $desc (已禁用)"
        fi
    done

    log_success "✅ $component_type 部署完成"
    return 0
}

deploy_sub_components() {
    local project_id="$1" namespace="$2" environment="$3" dry_run="$4"

    log_info "部署 celeryworker-tpl-admin-backend 子组件..."

    if [[ "${namespace_enabled:-true}" == "true" ]]; then
        scan_and_deploy_components "namespace" "$project_id" "$namespace" "$environment" "$dry_run" || return 1
    fi

    if [[ "${secrets_enabled:-true}" == "true" ]]; then
        scan_and_deploy_components "secret" "$project_id" "$namespace" "$environment" "$dry_run" || return 1
    fi

    if [[ "${configmap_enabled:-true}" == "true" ]]; then
        scan_and_deploy_components "configMap" "$project_id" "$namespace" "$environment" "$dry_run" || return 1
    fi

    if [[ "${middleware_enabled:-false}" == "true" ]]; then
        scan_and_deploy_components "middleware" "$project_id" "$namespace" "$environment" "$dry_run" || return 1
    fi

    if [[ "${ingress_enabled:-true}" == "true" ]]; then
        scan_and_deploy_components "ingress" "$project_id" "$namespace" "$environment" "$dry_run" || return 1
    fi

    log_success "✅ celeryworker-tpl-admin-backend 子组件部署完成"
    return 0
}

deploy_app() {
    log_info "开始部署 celeryworker-tpl-admin-backend..."
    log_info "环境: $ENVIRONMENT, 命名空间: $NAMESPACE"

    auto_generate_yaml "$CELERYWORKER_TPL_ADMIN_BACKEND_YAML" "$K8S_RESOURCE_DIR" || exit 1

    export CELERYWORKER_TPL_ADMIN_BACKEND_IMAGE_REGISTRY="${CELERYWORKER_TPL_ADMIN_BACKEND_IMAGE_REGISTRY:-$(get_cluster_harbor_registry)}"
    export CELERYWORKER_TPL_ADMIN_BACKEND_IMAGE_PROJECT="${CELERYWORKER_TPL_ADMIN_BACKEND_IMAGE_PROJECT:-app-images}"
    export CELERYWORKER_TPL_ADMIN_BACKEND_IMAGE="${CELERYWORKER_TPL_ADMIN_BACKEND_IMAGE:-tpl-admin-backend}"
    export CELERYWORKER_TPL_ADMIN_BACKEND_TAG="${CELERYWORKER_TPL_ADMIN_BACKEND_TAG:-1.0.0}"
    export IMAGE_PULL_POLICY="${IMAGE_PULL_POLICY:-Always}"
    export CELERYWORKER_TPL_ADMIN_BACKEND_IMAGE_PULL_SECRET_NAME="${CELERYWORKER_TPL_ADMIN_BACKEND_IMAGE_PULL_SECRET_NAME:-harbor-registry-secret}"
    export CELERYWORKER_TPL_ADMIN_BACKEND_FULL_IMAGE_NAME="${CELERYWORKER_TPL_ADMIN_BACKEND_IMAGE_REGISTRY}/${CELERYWORKER_TPL_ADMIN_BACKEND_IMAGE_PROJECT}/${CELERYWORKER_TPL_ADMIN_BACKEND_IMAGE}:${CELERYWORKER_TPL_ADMIN_BACKEND_TAG}"

    log_info "镜像: $CELERYWORKER_TPL_ADMIN_BACKEND_FULL_IMAGE_NAME"
    log_warn "⚠️  请确保该镜像已存在于 Harbor 仓库"

    export NAMESPACE="$NAMESPACE" ENV="$ENV" ENVIRONMENT="$ENVIRONMENT"
    export CELERYWORKER_TPL_ADMIN_BACKEND_FULL_IMAGE_NAME

    log_info "🚀 阶段1：部署子组件..."
    deploy_sub_components "$PROJECT_ID" "$NAMESPACE" "$ENVIRONMENT" false \
        || { log_error "❌ 子组件部署失败"; return 1; }

    log_info "🚀 阶段2：部署 celeryworker-tpl-admin-backend 核心服务..."

    if ! kubectl get nodes >/dev/null 2>&1; then
        log_warn "⚠️ 正在重新建立 Kubernetes 连接..."
        setup_kubectl_environment || { log_error "❌ 无法重新建立连接"; return 1; }
    fi

    auto_generate_yaml "$CELERYWORKER_TPL_ADMIN_BACKEND_YAML" "$K8S_RESOURCE_DIR" || return 1

    log_info "生成并部署 PVC..."
    auto_generate_yaml "$CELERYWORKER_TPL_ADMIN_BACKEND_PVC_YAML" "$K8S_RESOURCE_DIR" || return 1
    kubectl apply -f "$CELERYWORKER_TPL_ADMIN_BACKEND_PVC_YAML" -n "$NAMESPACE" \
        && log_success "PVC 部署完成" \
        || { log_error "PVC 部署失败"; return 1; }

    kubectl apply -f "$CELERYWORKER_TPL_ADMIN_BACKEND_YAML" -n "$NAMESPACE"

    if [ $? -eq 0 ]; then
        log_success "celeryworker-tpl-admin-backend 部署完成！"
        echo ""
        log_info "检查部署状态:"
        echo "  kubectl get pods -n $NAMESPACE -l app=celeryworker-tpl-admin-backend"
        echo "  kubectl logs -n $NAMESPACE -l app=celeryworker-tpl-admin-backend -f"
    else
        log_error "celeryworker-tpl-admin-backend 部署失败"
        exit 1
    fi
}

uninstall_app() {
    log_info "开始卸载 celeryworker-tpl-admin-backend..."

    log_info "🚀 阶段1：卸载核心服务..."
    if [ ! -f "$CELERYWORKER_TPL_ADMIN_BACKEND_YAML" ]; then
        log_warn "生成的 YAML 不存在，直接删除资源"
        kubectl delete deployment celeryworker-tpl-admin-backend -n "$NAMESPACE" --ignore-not-found=true
        kubectl delete service celeryworker-tpl-admin-backend -n "$NAMESPACE" --ignore-not-found=true
    else
        kubectl delete -f "$CELERYWORKER_TPL_ADMIN_BACKEND_YAML" -n "$NAMESPACE" --ignore-not-found=true
    fi
    log_success "✅ 核心服务卸载完成"

    log_info "🚀 阶段2：卸载子组件..."
    for component_type in "ingress" "middleware" "configMap" "secret"; do
        local base_dir="$PROJECT_ROOT/$component_type"
        [[ ! -d "$base_dir" ]] && continue
        for subdir in "$base_dir"/*/; do
            [[ ! -d "$subdir" ]] && continue
            local dirname
            dirname=$(basename "$subdir")
            local script_file="$subdir/deploy-${dirname}/deploy-${dirname}.sh"
            [[ "$component_type" == "ingress" ]] && script_file="$subdir/deploy-ingress/deploy-ingress.sh"
            [[ -f "$script_file" ]] && DISABLE_AUTO_CLEANUP=true bash "$script_file" uninstall "$PROJECT_ID" "$NAMESPACE" "$ENVIRONMENT" || true
        done
    done
    log_success "celeryworker-tpl-admin-backend 卸载完成！"
}

show_status() {
    log_info "celeryworker-tpl-admin-backend 状态:"
    echo ""
    echo "📦 Pods:"
    kubectl get pods -n "$NAMESPACE" -l app=celeryworker-tpl-admin-backend 2>/dev/null || echo "  无 Pod 运行"
    echo ""
    echo "🌐 Services:"
    kubectl get svc -n "$NAMESPACE" -l app=celeryworker-tpl-admin-backend 2>/dev/null || echo "  无 Service"
    echo ""
    echo "📋 Deployments:"
    kubectl get deployment -n "$NAMESPACE" -l app=celeryworker-tpl-admin-backend 2>/dev/null || echo "  无 Deployment"
    echo ""
    echo "📋 ConfigMaps:"
    kubectl get configmap -n "$NAMESPACE" -l app=celeryworker-tpl-admin-backend 2>/dev/null || echo "  无 ConfigMap"
    echo ""
    echo "🔐 Secrets:"
    kubectl get secret -n "$NAMESPACE" -l app=celeryworker-tpl-admin-backend 2>/dev/null || echo "  无 Secret"
    echo ""
    echo "📦 PVCs:"
    kubectl get pvc -n "$NAMESPACE" -l app=celeryworker-tpl-admin-backend 2>/dev/null || echo "  无 PVC"
}

main() {
    set -- "${ORIGINAL_ARGS[@]}"
    set -- "${PARSED_ARGS[@]}"

    [[ -n "${CLUSTER:-}" ]] && log_info "🎯 当前集群: ${CLUSTER}"

    local action="${1:-deploy}"
    local project_id="${2:-${DEFAULT_PROJECT_ID:-}}"
    local namespace="${3:-${DEFAULT_NAMESPACE:-}}"
    local environment="${4:-${DEFAULT_ENVIRONMENT:-}}"

    case "$environment" in
        "production"|"prod") ENV="prod" ;;
        *) ENV="dev" ;;
    esac

    ACTION="$action"
    PROJECT_ID="$project_id"
    NAMESPACE="$namespace"
    ENVIRONMENT="$environment"

    log_info "celeryworker-tpl-admin-backend 部署脚本启动"
    log_info "操作: $ACTION, 项目: $PROJECT_ID, 命名空间: $NAMESPACE, 环境: $ENVIRONMENT"

    check_kubectl

    case "$ACTION" in
        "deploy")
            read_k8s_config || { log_error "无法读取 Kubernetes 配置"; exit 1; }

            if kubectl get nodes >/dev/null 2>&1; then
                log_info "使用现有 Kubernetes 连接"
            else
                setup_kubectl_environment || { log_error "无法建立 Kubernetes 连接"; exit 1; }
                kubectl get nodes >/dev/null 2>&1 || { log_error "Kubernetes 连接不可用"; exit 1; }
            fi

            if [[ "${namespace_enabled:-true}" != "true" ]]; then
                check_namespace "$namespace" || exit 1
            fi

            deploy_app
            show_status
            ;;
        "uninstall")
            check_namespace "$namespace" || exit 1
            uninstall_app
            ;;
        "status")
            show_status
            ;;
        *)
            log_error "无效操作: $ACTION"
            echo "用法: $0 <deploy|uninstall|status> [project_id] [namespace] [environment]"
            echo "示例: $0 deploy sunmoonai app-platform-dev development"
            exit 1
            ;;
    esac
}

main "$@"

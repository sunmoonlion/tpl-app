#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TPL_APP_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

if [[ $# -lt 1 ]]; then
    echo "用法: $0 <app-name> [--output-dir DIR]" >&2
    exit 1
fi

APP_NAME="$1"
shift
OUTPUT_DIR="."

while [[ $# -gt 0 ]]; do
    case "$1" in
        --output-dir) OUTPUT_DIR="$2"; shift 2 ;;
        *) echo "未知参数: $1" >&2; exit 1 ;;
    esac
done

rename_tpl_paths() {
    local root="$1"
    find "$root" -depth -name "*tpl*" | while read -r path; do
        local dir base newbase
        dir="$(dirname "$path")"
        base="$(basename "$path")"
        newbase="${base//tpl/${APP_NAME}}"
        [[ "$base" == "$newbase" ]] || mv "$path" "$dir/$newbase"
    done
}

instantiate_worker() {
    local template_name="$1"
    local target_name="${template_name//tpl/${APP_NAME}}"
    local source_dir="$TPL_APP_ROOT/$template_name"
    local target_dir="$OUTPUT_DIR/$target_name"

    [[ -d "$source_dir" ]] || {
        echo "Worker 模板不存在: $source_dir" >&2
        exit 1
    }
    [[ ! -e "$target_dir" ]] || {
        echo "目标已存在，拒绝覆盖: $target_dir" >&2
        exit 1
    }

    cp -a "$source_dir" "$target_dir"
    find "$target_dir" -type f \
        ! -name "*.lock" \
        ! -name "pnpm-lock.yaml" \
        ! -name "CHANGELOG.md" \
        | while read -r file; do
            if grep -qE 'tpl|TPL|Tpl' "$file" 2>/dev/null; then
                sed -i \
                    -e "s/TPL/${APP_NAME^^}/g" \
                    -e "s/Tpl/${APP_NAME^}/g" \
                    -e "s/tpl/${APP_NAME}/g" \
                    "$file"
            fi
        done
    rename_tpl_paths "$target_dir"
    echo "Worker 已生成: $target_dir"
}

mkdir -p "$OUTPUT_DIR"
instantiate_worker "celeryworker-tpl-admin-backend"
instantiate_worker "nodebullworker-tpl-web-backend"

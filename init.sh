#!/usr/bin/env bash
# 将一个全新、可丢弃的 tpl-app 克隆原地转换为 Architecture v2 实例父仓。

set -euo pipefail

APP_NAME="${1:-}"
GITHUB_ORG="${2:-sunmoonlion}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

usage() {
  cat <<'EOF'
用法: ./init.sh <app-name> [github-org]
示例: ./init.sh tools sunmoonlion

警告: 本脚本会原地改写当前克隆，只能用于新建、可丢弃的 tpl-app 克隆。
EOF
}

if [[ ! "$APP_NAME" =~ ^[a-z][a-z0-9-]*$ ]] || [[ "$APP_NAME" == "tpl" ]]; then
  usage >&2
  exit 2
fi

cd "$SCRIPT_DIR"

if [[ "$(basename "$SCRIPT_DIR")" == "tpl-app" ]]; then
  echo "拒绝在名为 tpl-app 的权威模板目录原地执行；请先克隆到新目录。" >&2
  exit 2
fi

if [[ -n "$(git status --porcelain --untracked-files=no)" ]]; then
  echo "工作树不干净，拒绝实例化。" >&2
  exit 2
fi

ACTIVE_COMPONENTS=(backend admin-frontend web-frontend)
REFERENCE_COMPONENTS=(admin-frontend-react admin-frontend-vue web-backend-nest)

for component in "${ACTIVE_COMPONENTS[@]}"; do
  path="tpl-${component}"
  if [[ ! -d "$path" ]]; then
    echo "缺少默认模板组件: $path" >&2
    exit 2
  fi
  if [[ -n "$(git -C "$path" status --porcelain)" ]]; then
    echo "子模块工作树不干净: $path" >&2
    exit 2
  fi
done

replace_text_files() {
  local root="$1"
  while IFS= read -r -d '' file; do
    if LC_ALL=C grep -Iq . "$file" && grep -qE 'tpl|Tpl|TPL' "$file"; then
      sed -i \
        -e "s/TPL/${APP_NAME^^}/g" \
        -e "s/Tpl/${APP_NAME^}/g" \
        -e "s/tpl/${APP_NAME}/g" \
        "$file"
    fi
  done < <(
    find "$root" -type f -print0 \
      ! -path '*/.git' \
      ! -path '*/.git/*' \
      ! -name '*.lock' \
      ! -name 'pnpm-lock.yaml'
  )
}

rename_tpl_paths() {
  local root="$1"
  while IFS= read -r -d '' path; do
    local parent name replacement
    parent="$(dirname "$path")"
    name="$(basename "$path")"
    replacement="${name//tpl/$APP_NAME}"
    [[ "$name" == "$replacement" ]] || mv "$path" "$parent/$replacement"
  done < <(find "$root" -mindepth 1 -depth -name '*tpl*' -print0)
}

echo ">>> 实例化 $APP_NAME（GitHub organization: $GITHUB_ORG）"

for component in "${ACTIVE_COMPONENTS[@]}"; do
  replace_text_files "tpl-${component}"
  rename_tpl_paths "tpl-${component}"
done

for component in "${REFERENCE_COMPONENTS[@]}"; do
  if git ls-files --error-unmatch "tpl-${component}" >/dev/null 2>&1; then
    git submodule deinit -f -- "tpl-${component}" >/dev/null 2>&1 || true
    git rm -f "tpl-${component}"
  fi
done

cat > .gitmodules <<EOF
[submodule "${APP_NAME}-backend"]
\tpath = ${APP_NAME}-backend
\turl = https://github.com/${GITHUB_ORG}/${APP_NAME}-backend.git
[submodule "${APP_NAME}-admin-frontend"]
\tpath = ${APP_NAME}-admin-frontend
\turl = https://github.com/${GITHUB_ORG}/${APP_NAME}-admin-frontend.git
[submodule "${APP_NAME}-web-frontend"]
\tpath = ${APP_NAME}-web-frontend
\turl = https://github.com/${GITHUB_ORG}/${APP_NAME}-web-frontend.git
EOF

for component in "${ACTIVE_COMPONENTS[@]}"; do
  git mv "tpl-${component}" "${APP_NAME}-${component}"
done

# 锁文件不做通用文本扫描，只修正当前 workspace package identity。
uv_lock="${APP_NAME}-backend/app/uv.lock"
if [[ -f "$uv_lock" ]]; then
  sed -i -e "s/name = \"tpl-backend\"/name = \"${APP_NAME}-backend\"/g" "$uv_lock"
fi

for component in "${ACTIVE_COMPONENTS[@]}"; do
  git_dir=".git/modules/tpl-${component}"
  new_git_dir=".git/modules/${APP_NAME}-${component}"
  if [[ -d "$git_dir" && ! -e "$new_git_dir" ]]; then
    mv "$git_dir" "$new_git_dir"
  fi
  printf 'gitdir: ../.git/modules/%s-%s\n' "$APP_NAME" "$component" \
    > "${APP_NAME}-${component}/.git"
  if [[ -f "$new_git_dir/config" ]]; then
    sed -i \
      -e "s#../../../tpl-${component}#../../../${APP_NAME}-${component}#g" \
      -e "s#tpl-${component}\.git#${APP_NAME}-${component}.git#g" \
      "$new_git_dir/config"
  fi
done

git config --remove-section submodule.tpl-backend 2>/dev/null || true
git config --remove-section submodule.tpl-admin-frontend 2>/dev/null || true
git config --remove-section submodule.tpl-web-frontend 2>/dev/null || true
for component in "${ACTIVE_COMPONENTS[@]}"; do
  git config "submodule.${APP_NAME}-${component}.url" \
    "https://github.com/${GITHUB_ORG}/${APP_NAME}-${component}.git"
  git config "submodule.${APP_NAME}-${component}.active" true
done

git add .gitmodules \
  "${APP_NAME}-backend" \
  "${APP_NAME}-admin-frontend" \
  "${APP_NAME}-web-frontend"

echo ">>> 源码转换完成。"
echo ">>> 请先创建并推送三个子仓，再提交父仓 gitlink；部署清单由 k8s-scaffold-v2 生成。"

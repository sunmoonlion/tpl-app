#!/bin/bash
# init.sh — 从 tpl-app 模板初始化一个新项目
#
# 用法:
#   ./init.sh <app-name> [gitee-user]
#
# 示例:
#   ./init.sh investment sunmoonlion
#
# 效果:
#   - 在四个子模块和两个配套 Worker 模板内将 tpl / Tpl / TPL 替换为 <app-name>
#   - 在父仓根目录（maxdepth 含 .cursor/rules/、docs-* 等，排除模板实例目录）再替换一轮
#   - 重命名四个子模块和两个 Worker 目录，并修正各子模块 .git 指针
#   - 同步父仓 .git/modules/*、各子模块 module config、父仓 .git/config 与索引中的子模块路径（避免仅改目录名后子模块断裂）
#   - 更新 .gitmodules 中的远程 URL
#   - 完成后需手动将父目录 tpl-app 重命名为 <app-name>-app

set -e

APP_NAME="$1"
GITEE_USER="${2:-sunmoonlion}"

if [ -z "$APP_NAME" ]; then
  echo "用法: ./init.sh <app-name> [gitee-user]"
  echo "示例: ./init.sh investment sunmoonlion"
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# 原地改写文件（不依赖 GNU sed -i，macOS/BSD/Git Bash 均可）
patch_file() {
  local target="$1"
  shift
  local tmp="${target}.tmp.$$"
  sed "$@" "$target" > "$tmp" && mv "$tmp" "$target"
}

rename_tpl_paths() {
  local root="$1"
  find "$root" -depth -name "*tpl*" | while read -r path; do
    local dir base newbase
    dir="$(dirname "$path")"
    base="$(basename "$path")"
    newbase="${base//tpl/${APP_NAME}}"
    if [ "$base" != "$newbase" ]; then
      mv "$path" "$dir/$newbase"
    fi
  done
}

echo ">>> 初始化项目: $APP_NAME (Gitee 用户: $GITEE_USER)"

# 1. 替换四个子模块和两个配套 Worker 内部文件中的 tpl → app-name
echo ">>> [1/5] 替换模板实例内部文件..."
for dir in \
  tpl-admin-frontend \
  tpl-web-backend \
  tpl-web-frontend \
  tpl-admin-backend \
  nodebullworker-tpl-web-backend \
  celeryworker-tpl-admin-backend; do
  find "$SCRIPT_DIR/$dir" -type f \
    ! -path "*/.git" \
    ! -path "*/.git/*" \
    ! -path "*/app/prisma/clients/*" \
    ! -name "*.so" \
    ! -name "*.so.*" \
    ! -name "*.node" \
    ! -name "*.dll" \
    ! -name "*.dylib" \
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
  echo "    done: $dir"
done

# 1b. 替换父仓根目录文件中的 tpl → app-name（README、.mdc 规则、CLAUDE.md 等）
echo ">>> [1b/5] 替换父仓根目录文件..."
# maxdepth 需 ≥3，否则扫不到 .cursor/rules/*.mdc（三层路径：.cursor/rules/文件）
find "$SCRIPT_DIR" -maxdepth 4 -type f \
  ! -path "*/.git" \
  ! -path "*/.git/*" \
  ! -path "*/tpl-*/*" \
  ! -path "*/nodebullworker-tpl-*/*" \
  ! -path "*/celeryworker-tpl-*/*" \
  ! -path "*/k8s-scaffold/*" \
  ! -name "*.lock" \
  ! -name "pnpm-lock.yaml" \
  ! -name "CHANGELOG.md" \
  ! -name "init.sh" \
  | while read -r file; do
      if grep -qE 'tpl|TPL|Tpl' "$file" 2>/dev/null; then
        sed -i \
          -e "s/TPL/${APP_NAME^^}/g" \
          -e "s/Tpl/${APP_NAME^}/g" \
          -e "s/tpl/${APP_NAME}/g" \
          "$file"
      fi
    done
echo "    done: 父仓根目录"

# 2. 更新 .gitmodules
echo ">>> [2/5] 更新 .gitmodules..."
cat > "$SCRIPT_DIR/.gitmodules" <<EOF
[submodule "${APP_NAME}-admin-frontend"]
	path = ${APP_NAME}-admin-frontend
	url = https://gitee.com/${GITEE_USER}/${APP_NAME}-admin-frontend.git
[submodule "${APP_NAME}-web-backend"]
	path = ${APP_NAME}-web-backend
	url = https://gitee.com/${GITEE_USER}/${APP_NAME}-web-backend.git
[submodule "${APP_NAME}-web-frontend"]
	path = ${APP_NAME}-web-frontend
	url = https://gitee.com/${GITEE_USER}/${APP_NAME}-web-frontend.git
[submodule "${APP_NAME}-admin-backend"]
	path = ${APP_NAME}-admin-backend
	url = https://gitee.com/${GITEE_USER}/${APP_NAME}-admin-backend.git
EOF

# 3. 重命名子模块和 Worker 目录
echo ">>> [3/5] 重命名模板目录..."
mv "$SCRIPT_DIR/tpl-admin-frontend" "$SCRIPT_DIR/${APP_NAME}-admin-frontend"
mv "$SCRIPT_DIR/tpl-web-backend"    "$SCRIPT_DIR/${APP_NAME}-web-backend"
mv "$SCRIPT_DIR/tpl-web-frontend"   "$SCRIPT_DIR/${APP_NAME}-web-frontend"
mv "$SCRIPT_DIR/tpl-admin-backend"  "$SCRIPT_DIR/${APP_NAME}-admin-backend"
mv "$SCRIPT_DIR/nodebullworker-tpl-web-backend" "$SCRIPT_DIR/nodebullworker-${APP_NAME}-web-backend"
mv "$SCRIPT_DIR/celeryworker-tpl-admin-backend" "$SCRIPT_DIR/celeryworker-${APP_NAME}-admin-backend"
rename_tpl_paths "$SCRIPT_DIR/nodebullworker-${APP_NAME}-web-backend"
rename_tpl_paths "$SCRIPT_DIR/celeryworker-${APP_NAME}-admin-backend"

# 3b. 同步 admin-backend 的 uv.lock 工作区包名（*.lock 不参与 [1/5] 文本替换）
uv_lock="$SCRIPT_DIR/${APP_NAME}-admin-backend/app/uv.lock"
if [ -f "$uv_lock" ]; then
  patch_file "$uv_lock" -e "s/name = \"tpl-admin-backend\"/name = \"${APP_NAME}-admin-backend\"/g"
  echo "    patched uv.lock workspace package -> ${APP_NAME}-admin-backend"
fi

# 修正 .git 文件指向（子模块内的 .git 是文件，指向父仓库 modules 目录）
for sub in admin-frontend web-backend web-frontend admin-backend; do
  echo "gitdir: ../.git/modules/${APP_NAME}-${sub}" \
    > "$SCRIPT_DIR/${APP_NAME}-${sub}/.git"
done

# 4. 同步 Git 子模块元数据（否则仅改目录名会导致 .git/modules 仍为 tpl-*、索引仍为旧 path）
echo ">>> [4/5] 同步 Git 子模块元数据..."
MODULES_ROOT="$SCRIPT_DIR/.git/modules"
if [ -d "$MODULES_ROOT" ]; then
  for sub in admin-frontend web-backend web-frontend admin-backend; do
    oldm="$MODULES_ROOT/tpl-${sub}"
    newm="$MODULES_ROOT/${APP_NAME}-${sub}"
    if [ -d "$oldm" ] && [ ! -e "$newm" ]; then
      mv "$oldm" "$newm"
      echo "    renamed .git/modules/tpl-${sub} -> ${APP_NAME}-${sub}"
    elif [ -d "$newm" ]; then
      echo "    skip: .git/modules/${APP_NAME}-${sub} already exists"
    fi
  done
  for sub in admin-frontend web-backend web-frontend admin-backend; do
    modcfg="$MODULES_ROOT/${APP_NAME}-${sub}/config"
    if [ -f "$modcfg" ]; then
      patch_file "$modcfg" \
        -e "s#worktree = ../../../tpl-${sub}#worktree = ../../../${APP_NAME}-${sub}#g" \
        -e "s#tpl-${sub}\\.git#${APP_NAME}-${sub}.git#g"
    fi
  done
else
  echo "    skip: 无 .git/modules（非 Git 克隆时可忽略）"
fi

PARENT_GIT_CONFIG="$SCRIPT_DIR/.git/config"
if [ -f "$PARENT_GIT_CONFIG" ]; then
  for sub in admin-frontend web-backend web-frontend admin-backend; do
    patch_file "$PARENT_GIT_CONFIG" \
      -e "s#\\[submodule \"tpl-${sub}\"#\\[submodule \"${APP_NAME}-${sub}\"#g" \
      -e "s#tpl-${sub}\\.git#${APP_NAME}-${sub}.git#g"
  done
  patch_file "$PARENT_GIT_CONFIG" -e "s#tpl-app\\.git#${APP_NAME}-app.git#g"
  echo "    patched .git/config (submodules + 父仓 origin 中的 tpl-app 仓库名)"
else
  echo "    skip: 无 .git/config"
fi

if git -C "$SCRIPT_DIR" rev-parse --git-dir >/dev/null 2>&1; then
  git -C "$SCRIPT_DIR" add .gitmodules
  for d in tpl-admin-backend tpl-admin-frontend tpl-web-backend tpl-web-frontend; do
    if git -C "$SCRIPT_DIR" ls-files --error-unmatch "$d" >/dev/null 2>&1; then
      git -C "$SCRIPT_DIR" rm --cached -q "$d" || true
    fi
  done
  git -C "$SCRIPT_DIR" add \
    "${APP_NAME}-admin-backend" \
    "${APP_NAME}-admin-frontend" \
    "${APP_NAME}-web-backend" \
    "${APP_NAME}-web-frontend"
  git -C "$SCRIPT_DIR" add \
    "nodebullworker-${APP_NAME}-web-backend" \
    "celeryworker-${APP_NAME}-admin-backend"
  echo "    git index: 子模块路径已改为 ${APP_NAME}-*"
else
  echo "    skip: 当前目录不是 Git 仓库，未改索引"
fi

# 5. 提示重命名父目录
echo ""
echo ">>> [5/5] 完成！请手动将父目录重命名："
echo "    mv tpl-app ${APP_NAME}-app"
echo ""
echo ">>> 接下来还需要："
echo "    1. 在 Gitee 上将四个仓库改名为:"
echo "       ${APP_NAME}-admin-frontend"
echo "       ${APP_NAME}-web-backend"
echo "       ${APP_NAME}-web-frontend"
echo "       ${APP_NAME}-admin-backend"
echo "    2. 在父仓库执行: git submodule sync"
echo "    3. 分别进入各子模块提交改动"
echo "    4. 检查两个 Worker 的队列凭据与集群启用开关:"
echo "       nodebullworker-${APP_NAME}-web-backend"
echo "       celeryworker-${APP_NAME}-admin-backend"

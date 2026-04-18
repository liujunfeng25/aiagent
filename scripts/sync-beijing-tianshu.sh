#!/usr/bin/env bash
# 将「beijing」大屏（Vue3+Vite，产出目录 docs/）以 base=/tianshu/ 构建后同步到主前端 public/tianshu/，
# 供生产与 Docker 前端构建阶段一并打入 dist。
#
# 用法：
#   cd aiagent && ./scripts/sync-beijing-tianshu.sh
# 环境变量：
#   BEIJING_DIR  默认 $HOME/git项目预览/beijing（可改为你的克隆路径）
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
FRONTEND="$ROOT/frontend"
OUT="$FRONTEND/public/tianshu"
BEIJING_DIR="${BEIJING_DIR:-$HOME/git项目预览/beijing}"

if [[ ! -f "$BEIJING_DIR/package.json" ]]; then
  echo "未找到 beijing 项目：$BEIJING_DIR（请设置 BEIJING_DIR）" >&2
  exit 1
fi

echo "==> 构建 beijing（base=/tianshu/）…"
(
  cd "$BEIJING_DIR"
  if [[ ! -d node_modules ]]; then
    npm install --no-audit --no-fund
  fi
  npx vite build --base /tianshu/
)

echo "==> 同步到 $OUT"
rm -rf "$OUT"
mkdir -p "$FRONTEND/public"
cp -R "$BEIJING_DIR/docs" "$OUT"
echo "完成。请提交 public/tianshu（若需入库）或仅在本地/CI 构建镜像前执行本脚本。"

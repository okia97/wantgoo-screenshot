#!/usr/bin/env bash
# ============================================================
# 玩股網截圖系統 — 一鍵安裝腳本
# 執行方式：bash setup.sh
# ============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv"

echo "======================================"
echo " 玩股網截圖系統安裝程式"
echo "======================================"
echo ""

# ── 1. 確認 Python ──────────────────────────────────────────────

echo "[1/3] 確認 Python 版本..."
if ! command -v python3 &>/dev/null; then
    echo "錯誤：找不到 python3，請先安裝 Python 3.9+"
    exit 1
fi
PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo "      Python 版本：$PYTHON_VERSION"

# ── 2. 建立虛擬環境並安裝套件 ───────────────────────────────────

echo "[2/3] 建立 Python 虛擬環境並安裝套件..."
if [ -d "$VENV_DIR" ]; then
    echo "      虛擬環境已存在，跳過建立"
else
    python3 -m venv "$VENV_DIR"
fi
"$VENV_DIR/bin/pip" install --quiet --upgrade pip
"$VENV_DIR/bin/pip" install playwright Pillow
echo "      套件安裝完成"

# ── 3. 安裝 Chromium 並修正執行權限 ─────────────────────────────

echo "[3/3] 安裝 Playwright Chromium..."
"$VENV_DIR/bin/python" -m playwright install chromium

# 清除 macOS Gatekeeper 封鎖（確保 node / Chromium 可執行）
xattr -cr "$VENV_DIR/lib/python"*/site-packages/playwright/ 2>/dev/null || true
find "$VENV_DIR/lib" -path "*/playwright/driver/*" -type f \
    ! -name "*.py" ! -name "*.json" ! -name "*.txt" ! -name "*.md" ! -name "*.zip" \
    -exec chmod +x {} \; 2>/dev/null || true
echo "      Chromium 安裝完成"

# ── 完成 ────────────────────────────────────────────────────────

echo ""
echo "======================================"
echo " 安裝完成！"
echo "======================================"
echo ""
echo "截圖輸出：~/Desktop/玩股網截圖/<日期>/"
echo "執行記錄：$SCRIPT_DIR/logs/"
echo ""
echo "使用方式：雙擊「執行截圖.command」即可"
echo ""

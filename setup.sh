#!/usr/bin/env bash
# =============================================================================
#  Legal Argument Mining — установка
#  Использование: bash setup.sh [--skip-model]
#
#  Скрипт:
#    1. Инициализирует submodule ArgumentMining (Модуль I)
#    2. Создаёт виртуальное окружение и устанавливает зависимости
#    3. Скачивает GGUF-модель с Hugging Face (если не указан --skip-model)
# =============================================================================
set -e

# Репозиторий проекта
REPO="sichhhhh/LR_project"

SKIP_MODEL=false
for arg in "$@"; do
  [[ "$arg" == "--skip-model" ]] && SKIP_MODEL=true
done

# ── Читаем .env если есть ────────────────────────────────────────────────────
if [ -f ".env" ]; then
  # shellcheck disable=SC2046
  export $(grep -v '^#' .env | grep -v '^$' | xargs)
fi

# ── Параметры модели (можно переопределить через .env) ────────────────────────
HF_MODEL_REPO="${HF_MODEL_REPO:-google/gemma-3-4b-it-GGUF}"
HF_MODEL_FILE="${HF_MODEL_FILE:-gemma-3-4b-it-Q4_K_M.gguf}"
HF_TOKEN="${HF_TOKEN:-}"

echo "=============================================="
echo "  Legal Argument Mining — Setup"
echo "=============================================="

# ── 1. Submodule ──────────────────────────────────────────────────────────────
echo ""
echo "[1/4] Инициализация submodule ArgumentMining..."
git submodule update --init --recursive
echo "      OK"

# ── 2. Виртуальное окружение ──────────────────────────────────────────────────
echo ""
echo "[2/4] Создание виртуального окружения (.venv)..."
python3 -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate
echo "      OK"

# ── 3. Зависимости ────────────────────────────────────────────────────────────
echo ""
echo "[3/4] Установка зависимостей..."
pip install --upgrade pip --quiet
pip install -r requirements.txt --quiet
pip install huggingface_hub --quiet          # нужен для загрузки модели

if [ -f "ArgumentMining-main/requirements.txt" ]; then
  pip install -r ArgumentMining-main/requirements.txt --quiet
fi
echo "      OK"

# ── 4. Загрузка модели с Hugging Face ─────────────────────────────────────────
echo ""
if [ "$SKIP_MODEL" = true ]; then
  echo "[4/4] Загрузка модели пропущена (--skip-model)."
  echo "      Для запуска используйте --provider heuristic или --provider gemini."
elif [ -f "$HF_MODEL_FILE" ]; then
  echo "[4/4] Модель уже скачана: ${HF_MODEL_FILE} — пропуск."
else
  echo "[4/4] Загрузка модели с Hugging Face..."
  echo "      Репозиторий: ${HF_MODEL_REPO}"
  echo "      Файл:        ${HF_MODEL_FILE}"
  echo ""

  if [ -z "$HF_TOKEN" ]; then
    echo "  ВНИМАНИЕ: переменная HF_TOKEN не задана."
    echo "  Для моделей с ограниченным доступом (например, Gemma) нужен токен."
    echo "  Получить токен: https://huggingface.co/settings/tokens"
    echo "  Затем: скопируйте .env.example → .env и заполните HF_TOKEN=..."
    echo ""
    echo "  Если модель публичная — попробуем скачать без токена..."
  fi

  python3 - <<PYEOF
import sys
try:
    from huggingface_hub import hf_hub_download
    import os
    token = os.environ.get("HF_TOKEN") or None
    repo  = os.environ.get("HF_MODEL_REPO", "${HF_MODEL_REPO}")
    fname = os.environ.get("HF_MODEL_FILE", "${HF_MODEL_FILE}")
    print(f"  Скачиваю {fname} из {repo} ...")
    path = hf_hub_download(
        repo_id=repo,
        filename=fname,
        local_dir=".",
        token=token,
    )
    print(f"  Сохранено: {path}")
except Exception as e:
    print(f"  ОШИБКА при загрузке: {e}", file=sys.stderr)
    print("  Проверьте HF_TOKEN и HF_MODEL_REPO в файле .env", file=sys.stderr)
    sys.exit(1)
PYEOF
  echo "      OK"
fi

# ── Итог ──────────────────────────────────────────────────────────────────────
echo ""
echo "=============================================="
echo "  Установка завершена!"
echo "=============================================="
echo ""
echo "Запуск демо (модель и API-ключи не нужны):"
echo "  source .venv/bin/activate"
echo "  python pipeline/run_demo.py"
echo ""
echo "Полный пайплайн (локальная модель через Ollama):"
echo "  python pipeline/run_full_pipeline.py \\"
echo "      --input data/examples/example_input.jsonl \\"
echo "      --annotated data/examples/ \\"
echo "      --output output/ --provider ollama"
echo ""
echo "Полный пайплайн (Gemini API, ключ в .env → GOOGLE_AI_API_KEY):"
echo "  python pipeline/run_full_pipeline.py \\"
echo "      --annotated data/examples/example_input.jsonl \\"
echo "      --output output/ --provider gemini"

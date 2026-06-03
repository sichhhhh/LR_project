# Legal Argument Mining — Генератор юридических справок из графов

## Быстрый старт

```bash
# 1. Клонировать репозиторий вместе с submodule ArgumentMining (Модуль I)
git clone --recurse-submodules https://github.com/sichhhhh/LR_project.git
cd LR_project

# 2. Установить всё: окружение, зависимости, скачать модель (~5 ГБ)
#    Linux / Mac / Git Bash:
bash setup.sh
#    Windows (cmd):
#    setup.bat
#
#    Если модель не нужна (только эвристика или Gemini API):
#    bash setup.sh --skip-model

# 3. Запустить демо на встроенном примере
source .venv/bin/activate          # Windows: .venv\Scripts\activate
python pipeline/run_demo.py
```

**Ожидаемый вывод:**
```
Demo completed. Generated: output/brief_example.txt
```

Содержимое `output/brief_example.txt` — готовая аналитическая справка по примеру из `data/examples/`.

---

**Argument Mining** — субдисциплина NLP, сфокусированная на автоматическом извлечении и структурировании аргументации из неструктурированных текстов. Применительно к юридическим документам:

- нахождение тезисов (позиций сторон),
- оснований и доказательств,
- опровержений,
- построение логического графа рассуждения,
- перевод графа в понятный юристам документ.

**Задача данного модуля** — разработать алгоритм, который принимает на вход классифицированные аргументативные компоненты (результат модели Князева), устанавливает связи между ними и генерирует юридическую справку.

**Связанный репозиторий (Модуль I):** https://github.com/Seabas1/ArgumentMining

---

## Общая архитектура

```
Сырой правовой текст (.txt / .pdf)
         │
         ▼
┌─────────────────────────────────┐
│  Модуль I: Классификация        │  ← ruBERT-base (DeepPavlov)
│  аргументативных компонентов    │    Accuracy 77.8%, Macro F1 0.691
│  [репозиторий Князева]          │    predict.py → *.jsonl
└─────────────┬───────────────────┘
              │  JSONL: [{id, text, label, confidence, position}, ...]
              ▼
┌─────────────────────────────────┐
│  convert_jsonl_to_graph.py      │  ← Конвертация в JSON-граф (без рёбер)
└─────────────┬───────────────────┘
              │  JSON: {nodes: [...], edges: []}
              ▼
┌─────────────────────────────────┐
│  Модуль II: Relation Extraction │  ← Эвристики + LLM (Gemini / Ollama)
│  build_relations_llm.py         │
└─────────────┬───────────────────┘
              │  JSON: {nodes, edges: [{source, target, relation, confidence}]}
              ▼
┌─────────────────────────────────┐
│  Модуль III: Генератор справок  │  ← NetworkX + шаблонная генерация
│  generate_brief.py              │
└─────────────┬───────────────────┘
              │
              ▼
     Аналитическая справка (.txt / .docx)
```

## Модуль I — Классификация компонентов (Князев)

> Реализован в отдельном репозитории: https://github.com/Seabas1/ArgumentMining  
> Здесь описан формат его выходных данных — входа для `convert_jsonl_to_graph.py`.

### Формат выходных данных

```jsonl
{"doc_id": "doc_001", "position": 0, "text": "Истец просит признать договор недействительным.", "label": "CLAIM", "confidence": 0.92}
{"doc_id": "doc_001", "position": 1, "text": "Согласно ст. 168 ГК РФ, сделка ничтожна.", "label": "EVIDENCE", "confidence": 0.87}
{"doc_id": "doc_001", "position": 2, "text": "Ответчик полагает, что договор соответствует закону.", "label": "REBUTTAL", "confidence": 0.74}
```

### Метрики Модуля I

| Разметчик | Accuracy | Macro F1 |
|-----------|----------|----------|
| ruBERT (дообученная) | 77.8% | 0.691 |
| Qwen 3.5-9B (Ollama) | 66.1% | 0.566 |

---

## Модуль II — Построение связей

**Скрипт:** `module2_relations/build_relations_llm.py`

### Алгоритм

1. Загрузить JSON-граф с узлами (выход `convert_jsonl_to_graph.py`).
2. Отфильтровать `NON_ARG` — они не участвуют в связях.
3. Сформировать пары-кандидаты `(i, j)` с `|pos_i − pos_j| ≤ window`.
4. Определить тип связи:
   - **heuristic** (без API, всегда доступен): правила на основе меток
   - **gemini**: Gemini API (`GOOGLE_AI_API_KEY` в `.env`)
   - **ollama**: локальный Ollama-сервер
   - При ошибке LLM — автоматический fallback на эвристику.
5. Сохранить граф с заполненным полем `edges`.

### Запуск

```bash
# Эвристики (без API)
python module2_relations/build_relations_llm.py \
    --input  data/graphs/my_doc_nodes.json \
    --output data/graphs/my_doc_graph.json \
    --provider heuristic --window 5

# С Gemini API
python module2_relations/build_relations_llm.py \
    --input  data/graphs/my_doc_nodes.json \
    --output data/graphs/my_doc_graph.json \
    --provider gemini --window 5

# С Ollama
python module2_relations/build_relations_llm.py \
    --input  data/graphs/my_doc_nodes.json \
    --output data/graphs/my_doc_graph.json \
    --provider ollama --model qwen2.5:7b --window 5
```

### Параметры CLI

| Флаг | По умолчанию | Описание |
|------|-------------|----------|
| `--input` | — | JSON-граф с узлами |
| `--output` | — | JSON-граф с рёбрами |
| `--window` | `5` | Макс. расстояние между парами (предложений) |
| `--provider` | `ollama` | `heuristic` / `gemini` / `ollama` |
| `--model` | `None` | Имя модели для провайдера |

### Эвристические правила

| Пара (A → B) | Связь |
|-------------|-------|
| EVIDENCE / PREMISE → CLAIM | `support` |
| PREMISE → EVIDENCE / PREMISE | `support` |
| REBUTTAL → CLAIM / PREMISE / EVIDENCE | `attack` |
| CLAIM → CLAIM (с отрицанием в тексте) | `attack` |
| Всё остальное | `neutral` |

---

## Модуль III — Генератор справок

**Скрипты:** `module3_generator/generate_brief.py`, `graph_analyzer.py`, `mapping_rules.py`

### Запуск

```bash
# Текстовый формат
python module3_generator/generate_brief.py \
    --graph  data/graphs/my_doc_graph.json \
    --output output/brief.txt

# Word-документ
python module3_generator/generate_brief.py \
    --graph  data/graphs/my_doc_graph.json \
    --output output/brief.docx

# С Jinja2-шаблоном
python module3_generator/generate_brief.py \
    --graph    data/graphs/my_doc_graph.json \
    --output   output/brief.txt \
    --template module3_generator/templates/brief_template.txt
```

### Правила маппинга

| Секция справки | Правило |
|----------------|---------|
| **Позиция** | CLAIM с наибольшим числом исходящих `support`-рёбер |
| **Правовые основания** | EVIDENCE-узлы, достижимые по `support` от позиции |
| **Логические доводы** | PREMISE-узлы, достижимые по `support` от позиции |
| **Возражения** | Узлы с `attack`-рёбром в сторону позиции |
| **Вывод** | CLAIM с наибольшим числом входящих `support`-рёбер |

---

## Схема меток

### Компоненты аргументации (5 классов)

| Метка | Определение | Пример |
|-------|-------------|--------|
| `CLAIM` | Позиция, требование или вывод стороны / суда | «Суд считает требования истца обоснованными.» |
| `PREMISE` | Логическое обоснование без ссылки на норму | «Поскольку сделка совершена под принуждением...» |
| `EVIDENCE` | Ссылка на норму, документ или факт | «Согласно ст. 168 ГК РФ...» |
| `REBUTTAL` | Прямое опровержение чужой позиции | «Ответчик возражает, полагая, что...» |
| `NON_ARG` | Процедурный текст без аргументации | «Заседание состоялось 15 марта 2024 г.» |

Приоритет: `REBUTTAL > EVIDENCE > CLAIM > PREMISE > NON_ARG`

### Типы связей (3 класса)

| Метка | Описание | Пример |
|-------|----------|--------|
| `support` | A обосновывает B | EVIDENCE → CLAIM |
| `attack` | A опровергает B | REBUTTAL → CLAIM |
| `neutral` | Нет аргументативной связи | NON_ARG → * |

---

## Формат данных

### JSONL (вход конвертера)

```jsonl
{"doc_id": "doc_001", "position": 0, "text": "...", "label": "CLAIM", "confidence": 0.92}
```

### JSON-граф (между Модулями II и III)

```json
{
  "doc_id": "doc_001",
  "source_file": "example.jsonl",
  "metadata": {},
  "nodes": [
    {"id": "n0", "text": "...", "label": "CLAIM", "confidence": 0.92, "position": 0}
  ],
  "edges": [
    {"source": "n1", "target": "n0", "relation": "support", "confidence": 0.8}
  ]
}
```

Готовый пример: `data/examples/example_graph.json`.

---

## Установка и запуск

### Требования

Python 3.9+, Git.

### Локально (рекомендуется: через setup-скрипт)

```bash
git clone --recurse-submodules https://github.com/sichhhhh/LR_project.git
cd LR_project

# Linux / Mac / Git Bash:
bash setup.sh

# Windows (cmd):
setup.bat
```

Скрипт автоматически: создаёт `.venv`, устанавливает зависимости и скачивает модель с Hugging Face.

### Настройка токенов и API

```bash
cp .env.example .env
# Откройте .env в любом текстовом редакторе и заполните нужные поля.
```

**Как получить токен Hugging Face (нужен для загрузки модели):**

1. Зарегистрируйтесь на [huggingface.co](https://huggingface.co)
2. Откройте страницу модели и нажмите **«Agree and access repository»** (принятие лицензии)
3. Перейдите в [настройки токенов](https://huggingface.co/settings/tokens)
4. Нажмите **«New token»** → выберите тип **«Read»** → скопируйте токен
5. Вставьте в `.env`: `HF_TOKEN=hf_ваш_токен_здесь`

**Как получить ключ Gemini API** (бесплатная альтернатива локальной модели):

1. Откройте [aistudio.google.com/apikey](https://aistudio.google.com/apikey)
2. Нажмите **«Create API key»** → скопируйте ключ
3. Вставьте в `.env`: `GOOGLE_AI_API_KEY=ваш_ключ_здесь`
4. При запуске используйте флаг `--provider gemini`

### Демо без API и GPU

```bash
source .venv/bin/activate   # Windows: .venv\Scripts\activate
python pipeline/run_demo.py
# → output/brief_example.txt
```

### Полный пайплайн на своём документе

```bash
# 1. Конвертация JSONL → граф без рёбер
python convert_jsonl_to_graph.py \
    --input  data/annotated/my_doc.jsonl \
    --output data/graphs/my_doc_nodes.json

# 2. Построить связи (эвристики)
python module2_relations/build_relations_llm.py \
    --input  data/graphs/my_doc_nodes.json \
    --output data/graphs/my_doc_graph.json \
    --provider heuristic --window 5

# 3. Сгенерировать справку
python module3_generator/generate_brief.py \
    --graph  data/graphs/my_doc_graph.json \
    --output output/brief_my_doc.txt
```

### Google Colab

```python
!git clone --recurse-submodules https://github.com/sichhhhh/LR_project.git
%cd LR_project
!pip install -r requirements_colab.txt
!python pipeline/run_demo.py
```

### Тесты

```bash
pytest tests/
```

---

## Аппаратные требования

| Сценарий | GPU | RAM | Примечание |
|----------|-----|-----|------------|
| Демо / Модули II–III | — | 2 GB | Нет зависимости от GPU |
| С Ollama (qwen2.5:7b) | 8 GB VRAM | 16 GB | Нужен запущенный `ollama serve` |
| С Gemini API | — | 2 GB | Нужен `GOOGLE_AI_API_KEY` |
| Обучение модели (v0.2) | RTX 5060 8 GB | 16 GB | `train_relation_model.py` |

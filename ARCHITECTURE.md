# Архитектура проекта — Legal Argument Mining

## Общая схема пайплайна

```
Сырой правовой текст (.txt / .pdf)
         │
         ▼
┌─────────────────────────────────────┐
│  Модуль I: Классификация            │  ruBERT-base (DeepPavlov)
│  аргументативных компонентов        │  Отдельный репозиторий:
│  [github.com/Seabas1/ArgumentMining]│  predict.py → *.jsonl
└─────────────┬───────────────────────┘
              │  JSONL: [{id, text, label, confidence, position}, ...]
              ▼
┌─────────────────────────────────────┐
│  convert_jsonl_to_graph.py          │  Конвертация JSONL → JSON-граф
│  (nodes-only, без рёбер)            │  (без рёбер, только узлы)
└─────────────┬───────────────────────┘
              │  JSON: {nodes: [...], edges: []}
              ▼
┌─────────────────────────────────────┐
│  Модуль II: Relation Extraction     │  Эвристики + опционально LLM
│  module2_relations/                 │  (Gemini API / Ollama)
│  build_relations_llm.py             │
└─────────────┬───────────────────────┘
              │  JSON: {nodes: [...], edges: [{source,target,relation,confidence}]}
              ▼
┌─────────────────────────────────────┐
│  Модуль III: Генератор справок      │  NetworkX + шаблонная генерация
│  module3_generator/                 │  (опционально: Jinja2-шаблон)
│  generate_brief.py                  │
└─────────────┬───────────────────────┘
              │
              ▼
     Аналитическая справка (.txt / .docx)
```

---

## Структура файлов и их роли

```
legal-brief-generator/
│
├── convert_jsonl_to_graph.py          # Шаг 1: JSONL → JSON-граф (узлы без рёбер)
│
├── module2_relations/                 # Шаг 2: Relation Extraction
│   ├── __init__.py
│   ├── build_relations_llm.py         # Основной скрипт: строит рёбра между узлами
│   └── prompts/
│       ├── system_prompt.txt          # Системный промпт для LLM-режима
│       └── few_shot_ru.txt            # Few-shot примеры (русский)
│
├── module3_generator/                 # Шаг 3: Граф → Справка
│   ├── __init__.py
│   ├── graph_analyzer.py              # NetworkX: степени узлов, компоненты связности
│   ├── mapping_rules.py               # Правила: главный тезис, доказательства, возражения
│   ├── generate_brief.py              # Итоговая генерация текста / .docx
│   └── templates/
│       └── brief_template.txt         # Jinja2-шаблон справки
│
├── pipeline/
│   ├── run_demo.py                    # Быстрое демо на data/examples/
│   └── run_full_pipeline.py           # Полный пайплайн (I→II→III, требует Модуль I)
│
├── data/
│   ├── examples/
│   │   ├── example_input.jsonl        # Пример выхода Модуля I
│   │   └── example_graph.json         # Пример полного графа с рёбрами
│   ├── graphs/                        # JSON-графы (генерируются локально, в .gitignore)
│   ├── annotated/                     # JSONL из Модуля I (генерируются локально, в .gitignore)
│   └── relation_pairs/                # Датасет пар для обучения (будущий v0.2)
│
├── output/                            # Сгенерированные справки (в .gitignore)
├── model/relation_classifier/         # Веса обученной модели (в .gitignore)
│
├── tests/
│   ├── test_mapping_rules.py
│   ├── test_graph_analyzer.py
│   └── test_generate_brief.py
│
├── .env.example                       # Шаблон переменных окружения
├── requirements.txt                   # Зависимости (полный список)
├── requirements_colab.txt             # Минимальный набор для Google Colab
└── README.md
```

---

## Модуль II — build_relations_llm.py

### Алгоритм

1. Загрузить JSON-граф с узлами (выход `convert_jsonl_to_graph.py`).
2. Отфильтровать `NON_ARG` узлы — они не участвуют в связях.
3. Сформировать пары-кандидаты: `(i, j)` где `|pos_i − pos_j| ≤ window`.
4. Для каждой пары определить связь:
   - **heuristic** (по умолчанию и fallback): правила на основе меток
     - `EVIDENCE/PREMISE → CLAIM` = `support`
     - `REBUTTAL → CLAIM/PREMISE/EVIDENCE` = `attack`
     - остальное = `neutral`
   - **gemini**: запрос к Gemini API (`GOOGLE_AI_API_KEY` из `.env`)
   - **ollama**: запрос к локальному Ollama-серверу или CLI
5. Сохранить граф с заполненным полем `edges`.

### Параметры CLI

| Флаг | По умолчанию | Описание |
|------|-------------|----------|
| `--input` | — | JSON-граф с узлами |
| `--output` | — | JSON-граф с рёбрами |
| `--window` | `5` | Максимальное расстояние между парами (в предложениях) |
| `--provider` | `ollama` | `heuristic` / `gemini` / `ollama` |
| `--model` | `None` | Модель для провайдера (имя или путь к `.gguf`) |

---

## Модуль III — Генератор справок

### Правила маппинга (`mapping_rules.py`)

| Секция справки | Правило |
|----------------|---------|
| **Позиция (основной тезис)** | CLAIM с максимальным числом исходящих `support`-рёбер; при равенстве — ближайший к началу документа |
| **Правовые основания** | EVIDENCE-узлы, достижимые по `support`-рёбрам от основного тезиса |
| **Логические доводы** | PREMISE-узлы, достижимые по `support`-рёбрам от основного тезиса |
| **Возражения** | Все узлы с `attack`-рёбром в сторону основного тезиса |
| **Вывод** | CLAIM с максимальным числом входящих `support`-рёбер; при равенстве — ближайший к концу документа |

### Вывод

- `.txt` — простой текстовый формат (по умолчанию)
- `.docx` — Word-документ через `python-docx`
- Jinja2-шаблон — если передан `--template path/to/template.txt`

---

## Форматы данных

### JSONL (выход Модуля I / вход `convert_jsonl_to_graph.py`)

```jsonl
{"doc_id": "doc_001", "position": 0, "text": "...", "label": "CLAIM", "confidence": 0.92}
{"doc_id": "doc_001", "position": 1, "text": "...", "label": "EVIDENCE", "confidence": 0.87}
```

Поля: `doc_id`, `position` (порядковый номер предложения), `text`, `label` (`CLAIM` / `PREMISE` / `EVIDENCE` / `REBUTTAL` / `NON_ARG`), `confidence`.

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

Типы связей: `support` / `attack` / `neutral`.

---

## Зависимости

| Пакет | Для чего |
|-------|----------|
| `networkx` | Граф-анализ в Модуле III |
| `python-docx` | Генерация `.docx` справок |
| `google-generativeai` | `--provider gemini` |
| `requests` | `--provider ollama` (HTTP API) |
| `jinja2` | Шаблонная генерация справок |
| `pytest` | Тесты |

Зависимости Модуля I (`torch`, `transformers`, `razdel`) нужны **только** если используется `pipeline/run_full_pipeline.py` с флагом `--input` (автоматическая разметка через ArgumentMining-main).

---

## Дизайн-решения

- **Эвристики как fallback**: LLM-провайдер используется опционально. При отсутствии API-ключа или ошибке сети модуль автоматически переключается на правила меток. Это делает проект работоспособным без внешних API.
- **Разделение convert + build_relations**: Конвертация JSONL→JSON и построение связей вынесены в разные скрипты, чтобы можно было кешировать узлы и не перечитывать исходный файл при переборе параметров.
- **Несвязные графы**: Каждая слабо связная компонента обрабатывается как отдельный аргументативный блок.
- **Независимость от Модуля I**: Модули II и III работают от любого JSONL с нужными полями — не только от ruBERT из репозитория Князева.

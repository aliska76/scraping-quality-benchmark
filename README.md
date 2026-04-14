truth_text может быть мультиязычным, содержать структурированные данные, списки, цифры, а lie_text — это типичный футер/меню.

Ваша метрика F1 вычисляется скользящим окном по извлечённому тексту. Это значит:

Порядок слов имеет значение — окно ищет непрерывный блок текста, наиболее похожий на truth_text

Избыточный контод (весь HTML) размажет окно и снизит precision

Слишком агрессивная чистка может выбросить нужные предложения и снизить recall

Вывод: вам нужен адаптивный extractor, который пробует несколько стратегий и выбирает лучшую для каждого типа страницы.

Пошаговый план реализации (обновлённый)
Фаза 1: Базовый конвейер (быстрая победа)
Определить модели (ScrapeRequest, ScrapeResult)

Написать HTTP-запросчик с прокси (httpx)

Написать обёртку над trafilatura + readability

Запустить на первых 10 URL из train.csv

Оценить F1 через score.py

Фаза 2: Обнаружение типа страницы (роутинг)
Создать classifier.py, который определяет:

JSON API (Content-Type: application/json)

PDF (по URL или Content-Type)

SPA (мало текста после HTTP, но много после Playwright)

Статья / блог (много параграфов)

Каталог / список (много ссылок)

Фаза 3: Специализированные экстракторы
JsonExtractor — форматирует JSON в читаемый текст (важно для GeckoTerminal)

PdfExtractor — использует pypdf или pdfplumber

SpaExtractor — запускает Playwright + ждёт селекторы

ArticleExtractor — trafilatura с высокой чувствительностью

ListExtractor — извлекает все <li> и таблицы

Фаза 4: Ансамблевая стратегия
Пробовать несколько экстракторов и выбирать тот, у которого длина текста ближе к длине truth_text (в трейне) или максимальное покрытие без дублей (в тесте).

Категории сайтов (на основе test.csv)
Я проанализировал ваш test.csv и выделил реальные категории:

Категория	Признаки	Примеры из test.csv	Стратегия
PDF	.pdf в URL или Content-Type	#13, #20, #28, #84, #99, #110, #166, #316, #318, #361, #454, #483	Извлечь текст через pypdf
JSON API	/api/, .json, application/json	#14 (request_format~json), #108, #156, #374	Форматировать JSON → текст
Документация	/docs/, /api/, /reference/	#22, #54, #65, #92, #94, #129, #140, #148, #156, #193, #271, #312, #332, #348, #382	Trafilatura (обычно хорошо структурирована)
Статья/блог	/news/, /blog/, /story/, дата в URL	#26, #55, #76, #77, #117, #130, #131, #139, #142, #145, #160, #178, #197, #215, #216, #239, #248, #260, #261, #274, #285, #296, #333, #338, #352, #364, #379, #391, #416, #422, #423, #428, #435, #468, #469, #470, #488	Trafilatura (оптимизирован для текста)
Корпоративный сайт	/company/, /about/, /team/	#6, #169, #196, #209, #306, #424	Trafilatura + извлечение блоков
Магазин/товары	/products/, /shop/, /collections/, /item/	#2, #3, #29, #42, #85, #98, #115, #143, #150, #151, #172, #205, #254, #258, #259, #267, #315, #317, #388, #389, #399, #419, #444, #445, #475	Извлекать название, цену, описание (спец. экстрактор)
Социальная сеть	threads.net, instagram.com, twitter.com	#5	Playwright (требуют JS/логин)
Поисковик	duckduckgo.com, google.com, bing.com, yahoo.com	#1 (Geico — нет, это страховщик)	Добавить &nojs=1 или Playwright
Редирект	Статус 301/302, meta refresh, короткий HTML	#8 (длинный URL с passthru), #207	follow_redirects=True + извлечь финальный URL
Блок-страница	403, CAPTCHA, Cloudflare	#10 (Inc.com 403)	Сменить User-Agent, ротация прокси, Playwright
404/битая ссылка	Статус 404	#4 (karononline.com)	Просто вернуть статус
Другое	Всё остальное	#11, #12, #15, ...	Trafilatura + fallback на readability

Рекомендуемый алгоритм (сбалансированный)
text
1. Предварительная классификация по URL
   └── если известно → используем специализированный экстрактор

2. 1. Быстрый HTTP запрос (всегда)
   │
   ├─ Если статус 4xx/5xx → вернуть ошибку
   │
   ├─ Если Content-Type: application/pdf → PDF экстрактор
   │
   ├─ Если Content-Type: application/json → JSON экстрактор  
   │
   └─ Если HTML → Trafilatura
        │
        ├─ Если контент > 200 символов → ✅ ГОТОВО
        │
        └─ Если контент < 200 символов → Readability
             │
             ├─ Если контент > 200 символов → ✅ ГОТОВО
             │
             └─ Если всё ещё < 200 символов → Playwright или SELENIUM

3. Анализ HTML содержимого
   ├── если блок-страница → пробуем сменить User-Agent + повторить
   ├── если редирект → переходим по новому URL
   ├── если SPA (мало текста) → Playwright
   └── если обычная HTML → Trafilatura

4. Резервные стратегии (если контент пустой или <100 символов)
   ├── Readability (для статей)
   ├── Playwright (для JS-сайтов) или SELENIUM
   └── Raw text (извлечь весь текст без тегов)

Реалистичный бюджет: 5-10 секунд на URL в среднем. Для 500 URL это ~1 час. Приемлемо для тестового задания.

SRP (Single Responsibility Principle) архитектура
fetch() 
   ↓
1. Попытка: Прокси + Сжатие
   ↓
2. Если HTTP ошибка (502, 452, 403) → повтор: БЕЗ ПРОКСИ + Сжатие
   ↓
3. Декодируем результат
   ↓
4. Если кракозябры И включена опция → повтор:
   - Если шаг 1 или 2 дал успешный статус (но кракозябры)
   - Используем ТЕ ЖЕ НАСТРОЙКИ ПРОКСИ, что и в успешной попытке
   - НО без сжатия
   ↓
5. Возвращаем результат

retry_without_compression parameter:
Гибкость для разных сценариев
Сценарий	Рекомендуемое значение
Production (надежность важнее)	True
Тестирование (хотим увидеть проблемы)	False
Медленный интернет	False
Критичные данные (нельзя потерять)	True



# pipeline.py - только бизнес-логика, без реализации деталей

class ScraperPipeline:
    """
    Оркестрирует процесс скрейпинга:
    1. Получает URL
    2. Выбирает стратегию
    3. Извлекает контент
    4. Возвращает результат
    """

Полный поток данных
text
main.py
   │
   ├── читает config
   │
   ├── создаёт HTTPFetcher с параметрами из config
   │
   └── создаёт ScraperPipeline с HTTPFetcher
              │
              ▼
       pipeline.process()
              │
              ├── _fetch_with_retry()
              │        │
              │        └── http.fetch() ← вся умная логика внутри
              │
              ├── detect
              ├── extract
              ├── validate
              └── fallback


При выборе каждой библиотеки моими критериями были:
⭐ популярность (downloads / stars)
📜 лицензия (MIT / Apache — ок)
🧱 стабильность (не “pet project”)
🚀 подходит под задачу (а не просто “есть”)
стоимость библиотеки или запросов

проект должен работать и запускаться на windows и в macOS

основная сложность была в проработке кофигураций и продумывании их своевременном использовании


Запросы без прокси могут раскрыть ваш реальный IP — это опасно, особенно при скрейпинге. однако оставим такой конфиг для дебаггинга и долбанный Playwright

max_attempts тоже надо в параметр в Playwright в конфиге превратить

улучшения на будущее:
нужна ротация IP (разные прокси)

Стратегия fallback теперь:
1. HTTP запрос → (status, content)

2. Если content плохой (<500 символов) ИЛИ status != 200:
   → Пробуем браузер

3. Если браузер вернул хороший контент (>500 символов):
   → Берём статус И контент от браузера
   → ExtractMethod = браузер

4. Если браузер вернул плохой контент:
   → Возвращаемся к HTTP (статус и контент)
   → НО ExtractMethod = браузер (потому что пытались)



Python 3 Python 3.12.6
pip 24.2

## README.md

```markdown
# Tavily Scraping Assignment

Web scraping system for the Tavily Scraping Quality Benchmark assignment. Extracts clean content from 500 training URLs and 500 test URLs, balancing latency, accuracy, and cost.

## Features

- Async HTTP requests with proxy support and smart retry logic
- Browser-based fallback (Playwright) for JavaScript-heavy pages
- Optional Selenium fallback for compatibility
- Multi-format extraction: HTML, PDF, JSON
- Automatic content validation and quality scoring
- Configurable via JSON files
- Cross-platform (Windows / macOS)

## Requirements

- Python 3.12.6 or higher
- pip 24.2 or higher
- Internet connection (for downloading dependencies)

## Installation

```bash
python setup.py
```

The installer will:
- Install Python dependencies from `requirements.txt`
- Download Playwright Chromium browser
- Create required directories (`results/`, `logs/`, `data/`)

## Configuration

Edit files in the `config/` directory:

| File | Purpose |
|------|---------|
| `config/config.json` | Main settings (timeout, retries, browser options) |
| `config/user_agents.json` | User-Agent strings for rotation |

Key configuration parameters:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `timeout` | 10 | Request timeout in seconds |
| `max_concurrent` | 10 | Concurrent request limit |
| `min_content_length` | 500 | Minimum content length to consider good |
| `use_playwright` | false | Enable Playwright fallback |
| `use_selenium` | false | Enable Selenium fallback |
| `allow_direct_fallback` | false | Allow requests without proxy (dangerous) |

## Usage

### Basic Usage

```bash
# Test run (first 10 URLs)
python main.py --input train.csv --output results/train_results.jsonl --limit 10

# Full run (all URLs)
python main.py --input train.csv --output results/train_results.jsonl

# Run on test set
python main.py --input test.csv --output results/test_results.jsonl
```

### With Browser Fallback

```bash
# Enable Playwright
python main.py --input train.csv --output results/train_results.jsonl --use-playwright

# Or enable via config.json (set "use_playwright": true)
```

### Evaluate Results

```bash
python score.py --results results/train_results.jsonl --ground-truth train.csv
```

## Command Line Arguments

| Argument | Description |
|----------|-------------|
| `--input` | Input CSV file path (train.csv or test.csv) |
| `--output` | Output JSONL file path |
| `--limit` | Limit number of URLs to process (for testing) |
| `--use-playwright` | Enable Playwright for JavaScript rendering |
| `--max-concurrent` | Maximum concurrent requests (default: from config) |

## Project Structure

```
project/
├── config/                     # Configuration files
│   ├── config.json
│   └── user_agents.json
├── scraper/                   # Low-level fetching modules
│   ├── base.py                # Abstract fetcher interface
│   ├── fetcher.py             # HTTP fetcher (httpx)
│   ├── browser.py             # Playwright fetcher
│   └── selenium_browser.py    # Selenium fetcher (optional)
├── extractor.py               # Content extraction
├── validator.py               # Content quality validation
├── writer.py                  # JSONL output writer
├── pipeline.py                # Orchestration logic
├── models.py                  # Data models
├── logger.py                  # Metrics and statistics
├── config.py                  # Configuration loader
├── main.py                    # Entry point
├── setup.py                   # Cross-platform installer
└── requirements.txt           # Python dependencies
```

## Testing

```bash
# Run all tests
python -m pytest

# Run with coverage
python -m pytest --cov=. --cov-report=term

# Run specific test file
python -m pytest tests/test_fetcher.py -v
```

## Output Format

Results are saved in JSONL format (one JSON object per line):

```json
{"id": 1, "url": "https://...", "content": "extracted text...", "status_code": 200, "latency": 1.23}
```

## Troubleshooting

### Playwright browser not installed

```bash
python -m playwright install chromium
```

### Proxy connection issues

Check that `proxy.json` exists and has the correct format. The system uses port 65534 for HTTP requests.

### Selenium not working

Make sure Chrome is installed. The `webdriver-manager` will download the appropriate ChromeDriver automatically.

## License

MIT (for assignment purposes)
```
# HH.ru MCP Server

MCP сервер для автоматизации поиска работы на hh.ru через AI (Claude Code, Gemini CLI, Cursor и др.)

## Возможности

- Поиск вакансий с фильтрами (регион, зарплата, опыт, график)
- Просмотр деталей вакансии
- Получение списка резюме
- Отклик на вакансии с сопроводительным письмом
- Поднятие резюме в поиске
- Просмотр откликов и приглашений
- Интеграция с портфолио проектов

## Требования

- Python 3.10+
- [uv](https://docs.astral.sh/uv/) (рекомендуется) или pip

## Быстрый старт

### 1. Клонировать репозиторий

```bash
git clone https://github.com/Kirill552/hh-mcp.git
cd hh-mcp
```

### 2. Установить зависимости

```bash
# Создать виртуальное окружение
uv venv
# или: python -m venv .venv

# Активировать
# Windows:
.venv\Scripts\activate
# Linux/Mac:
source .venv/bin/activate

# Установить зависимости
uv pip install fastmcp "hh-applicant-tool[playwright]"
# или: pip install fastmcp "hh-applicant-tool[playwright]"

# Установить браузер для авторизации
playwright install chromium
```

### 3. Авторизоваться на hh.ru

**Не нужно регистрировать приложение на dev.hh.ru!**

Используются credentials Android-приложения hh.ru (встроены в hh-applicant-tool).

```bash
hh-applicant-tool authorize
```

Откроется браузер → вводишь email/телефон → получаешь код из SMS → готово.

Токен сохраняется локально, повторная авторизация не нужна.

### 4. Настроить профиль

```bash
# Скопировать пример
cp profile.example.json profile.json

# Отредактировать profile.json — указать свои данные:
# - name, contacts — для сопроводительных писем
# - projects_path — путь к папке с проектами (для PORTFOLIO.md)
# - tech_stack, strengths — для генерации писем
```

### 5. Подключить к AI

#### Claude Code

Добавь в `~/.claude/settings.json`:

```json
{
  "mcpServers": {
    "hh-tool": {
      "command": "uv",
      "args": ["run", "python", "/path/to/hh-mcp/hh_mcp_server.py"]
    }
  }
}
```

#### Gemini CLI

Добавь в `~/.gemini/settings.json`:

```json
{
  "mcpServers": {
    "hh-tool": {
      "command": "uv",
      "args": ["run", "python", "/path/to/hh-mcp/hh_mcp_server.py"]
    }
  }
}
```

#### Cursor

Добавь в `.cursor/mcp.json` в корне проекта или глобально:

```json
{
  "mcpServers": {
    "hh-tool": {
      "command": "uv",
      "args": ["run", "python", "/path/to/hh-mcp/hh_mcp_server.py"]
    }
  }
}
```

**Windows:** замени путь на `C:\\Users\\username\\path\\to\\hh-mcp\\hh_mcp_server.py`

## Использование

```
> Найди вакансии Python разработчика в Москве, удалёнка, от 200к
> Покажи детали первой вакансии
> Откликнись на неё с письмом про мой опыт в backend разработке
```

## Доступные инструменты

| Инструмент | Описание | Требует авторизации |
|------------|----------|---------------------|
| `check_auth` | Проверить статус авторизации | Нет |
| `search_vacancies` | Поиск вакансий | Нет |
| `get_vacancy_details` | Детали вакансии | Нет |
| `get_candidate_profile` | Профиль кандидата из profile.json | Нет |
| `get_portfolio_projects` | Проекты из PORTFOLIO.md | Нет |
| `get_areas` | Список регионов | Нет |
| `get_dictionaries` | Справочники (опыт, график) | Нет |
| `get_my_resumes` | Список резюме | **Да** |
| `get_resume_details` | Детали резюме | **Да** |
| `apply_to_vacancy` | Откликнуться | **Да** |
| `update_resume` | Поднять резюме | **Да** |
| `edit_resume` | Редактировать резюме | **Да** |
| `get_negotiations` | Список откликов | **Да** |

## Параметры поиска

### Регионы (area)

| ID | Регион |
|----|--------|
| 113 | Россия (вся) |
| 1 | Москва |
| 2 | Санкт-Петербург |
| 1001 | Москва и МО |

### Опыт работы (experience)

| Значение | Описание |
|----------|----------|
| noExperience | Нет опыта |
| between1And3 | От 1 до 3 лет |
| between3And6 | От 3 до 6 лет |
| moreThan6 | Более 6 лет |

### График (schedule)

| Значение | Описание |
|----------|----------|
| fullDay | Полный день |
| remote | Удалённая работа |
| flexible | Гибкий график |
| shift | Сменный график |

## Портфолио проектов

Для интеграции портфолио создай файлы `PORTFOLIO.md` в папках проектов:

```
projects_path/
├── project1/
│   └── PORTFOLIO.md
├── project2/
│   └── PORTFOLIO.md
```

Формат PORTFOLIO.md:

```markdown
---
project: my-project
status: production
relevance: high
---

# My Project

## Что это
Описание проекта

## Tech Stack
- **Backend:** Python, FastAPI
- **Frontend:** React

## Для резюме
Разработал веб-приложение с использованием FastAPI и React
```

## Troubleshooting

### "Не авторизован"

```bash
hh-applicant-tool authorize
```

### "hh-applicant-tool not found"

```bash
pip install "hh-applicant-tool[playwright]"
playwright install chromium
```

### "profile.json не найден"

```bash
cp profile.example.json profile.json
# Отредактируй profile.json
```

### Токен истёк

Токен автоматически обновляется. Если не работает — повтори авторизацию.

## Лицензия

MIT

## Credits

- [hh-applicant-tool](https://github.com/s3rgeym/hh-applicant-tool) — авторизация и API клиент
- [FastMCP](https://github.com/jlowin/fastmcp) — фреймворк для MCP серверов

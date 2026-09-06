# MyIIS MCP Server

[![CI / Tests](https://img.shields.io/badge/tests-14%20passed-brightgreen.svg)]()
[![Python](https://img.shields.io/badge/python-3.12%2B-blue.svg)]()
[![MCP](https://img.shields.io/badge/MCP-2.1%2B-purple.svg)]()
[![License](https://img.shields.io/badge/license-MIT-green.svg)]()

> **MyIIS MCP** — официальный Model Context Protocol (MCP) сервер, предоставляющий ChatGPT и другим LLM-клиентам доступ в реальном времени к расписанию занятий, учебным неделям, группам и преподавателям Белорусского государственного университета информатики и радиоэлектроники ([ИИС БГУИР](https://iis.bsuir.by/api)).

---

## 🏛 Архитектура

MyIIS MCP спроектирован как ультратонкий, высокопроизводительный и асинхронный адаптер между протоколом **Streamable HTTP MCP** (требуемым OpenAI / ChatGPT Developer Mode) и открытым REST API ИИС БГУИР:

```mermaid
flowchart LR
    subgraph Clients["Клиенты"]
        ChatGPT["ChatGPT / Developer Mode"]
        Inspector["MCP Inspector"]
    end

    subgraph Hosting["Vercel Production (portfolio-site)"]
        Domain["https://myiis.ordinad.xyz/mcp"]
        VercelFn["Python Serverless Function (api/mcp.py)"]
        Submodule["Git Submodule: vendor/myiis-mcp"]
    end

    subgraph Core["MyIIS MCP Core"]
        MCPServer["MCPServer (Streamable HTTP / ASGI)"]
        Service["ScheduleService (Date & Week Engine)"]
        BSUIRClient["BSUIRClient (httpx async)"]
    end

    subgraph External["Внешние сервисы"]
        BSUIR["Официальный API ИИС БГУИР (iis.bsuir.by/api/v1)"]
    end

    ChatGPT --> Domain
    Inspector --> Domain
    Domain --> VercelFn
    VercelFn --> Submodule
    Submodule --> MCPServer
    MCPServer --> Service
    Service --> BSUIRClient
    BSUIRClient --> BSUIR
```

### Ключевые принципы архитектуры:
- **Serverless & Stateless**: сервер не хранит постоянного состояния между вызовами, идеально работает в среде Vercel Serverless Functions.
- **Официальный MCP Python SDK 2.x**: полная поддержка спецификации протокола Streamable HTTP, `structuredContent`, аннотаций (`readOnlyHint: true`, `destructiveHint: false`, `openWorldHint: false`) и схем `outputSchema`.
- **Нормализация данных**: вместо огромных "сырых" JSON-ответов БГУИР сервер формирует компактные, строгие Pydantic-модели, удобные как для генерации текста языковой моделью, так и для будущего MCP Apps UI.
- **Интеллектуальный расчет недель**: сервер автоматически рассчитывает 4-недельный цикл БГУИР для любой целевой даты («сегодня», «завтра», произвольная дата) на основе текущей недели университета.

---

## 🛠 Доступные MCP Tools

Все инструменты строго `read-only` и не изменяют состояние.

| Tool | Описание | Основные аргументы |
|------|----------|-------------------|
| `get_group_schedule` | Получить расписание учебной группы (на день, диапазон дней или всю неделю) | `group` (номер группы), `date` ('today', 'tomorrow', 'ГГГГ-ММ-ДД'), `days` (1-14), `subgroup` (1 или 2) |
| `get_teacher_schedule` | Получить расписание занятий преподавателя по фамилии или urlId | `teacher` (фамилия или urlId), `date`, `days` |
| `search_groups` | Поиск учебных групп по номеру, специальности или факультету | `query` (строка поиска), `course` (1-5), `faculty` (аббревиатура) |
| `search_teachers` | Поиск преподавателей по фамилии, имени или кафедре | `query` (ФИО), `department` (кафедра) |
| `get_current_week` | Получить текущую учебную неделю БГУИР (1-4) и дату | *без аргументов* |

### Структура ответа занятия (`NormalizedLesson`):
```json
{
  "subject": "ЭМП",
  "subject_full_name": "Эргономика мобильных приложений",
  "lesson_type": "ЛК",
  "start_time": "08:30",
  "end_time": "09:55",
  "date": "2026-09-07",
  "day_of_week": "Понедельник",
  "week_numbers": [1, 3],
  "subgroup": 0,
  "auditories": ["112-3 к."],
  "building": "3",
  "teachers": ["Василькова А. Н."],
  "groups": ["310101"],
  "note": null
}
```

---

## 💬 Примеры запросов к ChatGPT

После подключения MyIIS MCP в ChatGPT пользователь может задавать запросы на естественном языке:

- *«Какое расписание у группы 310101 на сегодня?»*
- *«Какие пары завтра у 310101 для первой подгруппы?»*
- *«Покажи расписание занятий преподавателя Васильковой на понедельник»*
- *«Какая сейчас идет учебная неделя в БГУИР?»*
- *«Найди группы факультета ФКП по специальности ИСиТ»*
- *«Кто ведет занятия на кафедре ПОИТ?»*

---

## 💻 Локальная установка и запуск

### Требования
- Python 3.12+
- `uv` или стандартный `pip`
- Node.js 18+ (для запуска MCP Inspector)

### 1. Клонирование и установка зависимостей
```bash
git clone https://github.com/OrDinaD/myiis-mcp.git
cd myiis-mcp

# Создание виртуального окружения и установка
uv venv .venv
source .venv/bin/activate
uv pip install -e ".[dev]"
```

### 2. Запуск тестов
```bash
pytest
```

### 3. Локальный запуск сервера
```bash
uvicorn myiis_mcp.server:app --host 127.0.0.1 --port 8000 --reload
```

После запуска доступны:
- Healthcheck: `http://127.0.0.1:8000/health`
- Discovery: `http://127.0.0.1:8000/`
- Streamable HTTP MCP Endpoint: `http://127.0.0.1:8000/mcp`

### 4. Тестирование через официальный MCP Inspector
Запустите интерактивный веб-интерфейс MCP Inspector:
```bash
npx @modelcontextprotocol/inspector
```
В открывшемся интерфейсе выберите transport: **Streamable HTTP**, URL: `http://127.0.0.1:8000/mcp`.

Либо через CLI:
```bash
npx @modelcontextprotocol/inspector --cli --transport http --server-url http://127.0.0.1:8000/mcp --method tools/list --strict
```

---

## 🚀 Развертывание на Vercel и интеграция с Portfolio_site

Для оптимизации квот Vercel и хостинга поддомена `myiis.ordinad.xyz` проект развернут в рамках существующего production Vercel-проекта `portfolio-site` ([ordinad.xyz](https://ordinad.xyz)).

### Схема интеграции через Git Submodule:
1. Репозиторий `OrDinaD/myiis-mcp` является единственным **Source of Truth** для кода MCP.
2. Репозиторий `OrDinaD/Portfolio_site` содержит `myiis-mcp` как **Git Submodule**:
   ```bash
   git submodule add https://github.com/OrDinaD/myiis-mcp.git vendor/myiis-mcp
   ```
3. В `Portfolio_site` добавлен минимальный Vercel Python entrypoint `api/mcp.py`:
   ```python
   import os, sys
   sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "vendor", "myiis-mcp"))
   from myiis_mcp.server import app
   ```
4. В `vercel.json` настроен routing:
   - Запросы к `/mcp` и `/health` перенаправляются в `api/mcp.py`.
   - Основной сайт `ordinad.xyz` продолжает работать на Vite/React без изменений.

### Production URLs:
- **MCP Endpoint**: `https://myiis.ordinad.xyz/mcp` (также доступен по `https://ordinad.xyz/mcp`)
- **Healthcheck**: `https://myiis.ordinad.xyz/health`

---

## 🤖 Подключение в ChatGPT Developer Mode

1. Откройте ChatGPT (с активной подпиской Plus / Team / Pro).
2. Перейдите в **Settings** → **Security and login** → включите **Developer mode**.
3. Откройте [chatgpt.com/plugins](https://chatgpt.com/plugins) или меню плагинов.
4. Нажмите **Add an MCP server** (+).
5. Задайте имя: `MyIIS`.
6. В поле **Server URL** укажите production endpoint:
   ```text
   https://myiis.ordinad.xyz/mcp
   ```
7. ChatGPT подключится по Streamable HTTP, считает манифест инструментов (`tools/list`) и сделает расписание доступным в диалоге!

---

## 🔮 Phase 2 — MCP Apps UI (Interactive Schedule Widget)

В соответствии со спецификацией **OpenAI Apps SDK** и **MCP Apps** (`@modelcontextprotocol/ext-apps`):
- Следующим этапом развития является добавление интерактивного визуального компонента (Schedule Widget), который будет рендериться прямо в чате ChatGPT в виде интерактивной карточки расписания (календарь, выбор дня, переключение недель 1-4, подсветка текущей пары).
- Архитектура `myiis_mcp` уже подготовлена к этому:
  - Все tools возвращают `structuredContent`, совместимый со схемой виджета.
  - В `_meta` инструментов будет добавлен ресурс `ui://widget/schedule.html`.
  - Виджет будет использовать `window.openai` bridge для адаптивной темы и фильтрации.

---

## 🔮 Phase 3 — Сохранение группы и персонализация

- Поддержка ChatGPT Memory для автоматического запоминания номера группы пользователя (без необходимости вводить его каждый раз).
- В будущем: опциональный OAuth для доступа к персональному кабинету студента (зачетка, рейтинг, ведомости).

---

## 📄 Источник данных и лицензия

- Данные предоставляются открытым API Интегрированной Информационной Системы БГУИР: [iis.bsuir.by/api](https://iis.bsuir.by/api).
- Код сервера распространяется под лицензией **MIT**. Автор: [Vladislav Vasilevskiy](https://github.com/OrDinaD).

"""
HH.ru MCP Server - автоматизация поиска работы через AI

Использует hh-applicant-tool для авторизации (не нужно регистрировать приложение на dev.hh.ru)

Перед использованием:
1. pip install 'hh-applicant-tool[playwright]'
2. hh-applicant-tool authorize  (авторизоваться один раз)
3. Скопировать profile.example.json -> profile.json и заполнить свои данные
4. Запустить этот MCP сервер
"""

from fastmcp import FastMCP
import json
import sys
import os
from pathlib import Path

try:
    from hh_applicant_tool.api.client import ApiClient, OAuthClient
    from hh_applicant_tool.api.client_keys import ANDROID_CLIENT_ID, ANDROID_CLIENT_SECRET
    from hh_applicant_tool.utils.config import Config, get_config_path
    HH_TOOL_AVAILABLE = True
except ImportError:
    HH_TOOL_AVAILABLE = False
    print("Warning: hh-applicant-tool not found. Install: pip install 'hh-applicant-tool[playwright]'", file=sys.stderr)


def get_profile_path() -> Path:
    """Путь к profile.json"""
    return Path(__file__).parent / "profile.json"


def load_profile() -> dict | None:
    """Загрузить профиль пользователя из profile.json"""
    path = get_profile_path()
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

# Создаём MCP сервер
mcp = FastMCP(
    "hh-tool",
    instructions="""
    Ты - помощник для поиска работы на hh.ru.

    ПОРЯДОК РАБОТЫ ПРИ ОТКЛИКЕ:
    1. search_vacancies — поиск вакансий
    2. get_vacancy_details — детали выбранной вакансии
    3. get_candidate_profile — профиль кандидата (навыки, позиционирование)
    4. get_portfolio_projects(relevance="high") — проекты для резюме
    5. Генерация персонализированного письма
    6. apply_to_vacancy — отклик с письмом

    ПРАВИЛА ГЕНЕРАЦИИ ПИСЬМА:
    - Используй шаблон из get_candidate_profile
    - Выбери 2-3 проекта релевантных требованиям вакансии
    - Бери готовые фразы из секции "Для резюме" в PORTFOLIO.md
    - НЕ упоминай то, что указано в do_not_mention профиля

    Всегда показывай вакансии пользователю перед откликом.
    """
)

# Глобальный клиент API
_api_client = None
_config = None


def get_config_file_path():
    """Путь к config.json hh-applicant-tool"""
    return get_config_path() / "hh-applicant-tool" / "config.json"


def get_client() -> ApiClient:
    """Получить авторизованный клиент API"""
    global _api_client, _config

    if _api_client is not None:
        return _api_client

    if HH_TOOL_AVAILABLE:
        # Читаем токен из config.json
        _config = Config(get_config_file_path())
        token = _config.get("token", {})

        if token and token.get("access_token"):
            _api_client = ApiClient(
                access_token=token.get("access_token"),
                refresh_token=token.get("refresh_token"),
                access_expires_at=token.get("access_expires_at", 0),
                client_id=ANDROID_CLIENT_ID,
                client_secret=ANDROID_CLIENT_SECRET,
            )
            return _api_client

    # Без авторизации (только поиск)
    _api_client = ApiClient()
    return _api_client


def save_token():
    """Сохранить обновлённый токен"""
    global _api_client, _config
    if _config and _api_client:
        _config.save(token=_api_client.get_access_token())


@mcp.tool()
def check_auth() -> str:
    """
    Проверить статус авторизации

    Returns:
        Статус авторизации и инструкции если не авторизован
    """
    client = get_client()

    if client.access_token:
        # Попробуем получить информацию о пользователе
        try:
            me = client.get("/me")
            return json.dumps({
                "authorized": True,
                "user": {
                    "id": me.get("id"),
                    "name": f"{me.get('first_name', '')} {me.get('last_name', '')}".strip(),
                    "email": me.get("email"),
                }
            }, ensure_ascii=False, indent=2)
        except Exception as e:
            return json.dumps({
                "authorized": False,
                "error": str(e),
                "instruction": "Выполните: hh-applicant-tool authorize"
            }, ensure_ascii=False, indent=2)

    return json.dumps({
        "authorized": False,
        "instruction": "Для откликов нужна авторизация. Выполните в терминале: hh-applicant-tool authorize"
    }, ensure_ascii=False, indent=2)


@mcp.tool()
def search_vacancies(
    text: str,
    area: str = "113",
    salary: int | None = None,
    only_with_salary: bool = False,
    experience: str | None = None,
    employment: str | None = None,
    schedule: str | None = None,
    per_page: int = 10
) -> str:
    """
    Поиск вакансий на hh.ru

    Args:
        text: Поисковый запрос (например "Python разработчик")
        area: ID региона (1=Москва, 2=СПб, 113=Россия). По умолчанию вся Россия.
        salary: Желаемая зарплата
        only_with_salary: Только вакансии с указанной зарплатой
        experience: Опыт работы (noExperience, between1And3, between3And6, moreThan6)
        employment: Тип занятости (full, part, project, volunteer, probation)
        schedule: График работы (fullDay, shift, flexible, remote, flyInFlyOut)
        per_page: Количество результатов (макс 100)

    Returns:
        JSON со списком вакансий
    """
    client = get_client()

    params = {
        "text": text,
        "area": area,
        "per_page": min(per_page, 100),
    }

    if salary:
        params["salary"] = salary
    if only_with_salary:
        params["only_with_salary"] = "true"
    if experience:
        params["experience"] = experience
    if employment:
        params["employment"] = employment
    if schedule:
        params["schedule"] = schedule

    try:
        data = client.get("/vacancies", params)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)

    # Форматируем результат
    vacancies = []
    for v in data.get("items", []):
        salary_info = "Не указана"
        if v.get("salary"):
            s = v["salary"]
            from_sal = s.get('from', '')
            to_sal = s.get('to', '')
            currency = s.get('currency', 'RUR')
            if from_sal and to_sal:
                salary_info = f"{from_sal}-{to_sal} {currency}"
            elif from_sal:
                salary_info = f"от {from_sal} {currency}"
            elif to_sal:
                salary_info = f"до {to_sal} {currency}"

        vacancies.append({
            "id": v["id"],
            "name": v["name"],
            "company": v["employer"]["name"],
            "salary": salary_info,
            "area": v["area"]["name"],
            "url": v["alternate_url"],
            "schedule": v.get("schedule", {}).get("name", "Не указан"),
            "experience": v.get("experience", {}).get("name", "Не указан"),
        })

    result = {
        "found": data.get("found", 0),
        "pages": data.get("pages", 0),
        "vacancies": vacancies
    }

    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool()
def get_vacancy_details(vacancy_id: str) -> str:
    """
    Получить подробную информацию о вакансии

    Args:
        vacancy_id: ID вакансии

    Returns:
        Подробная информация о вакансии
    """
    client = get_client()

    try:
        v = client.get(f"/vacancies/{vacancy_id}")
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)

    # Убираем HTML теги из описания
    import re
    description = v.get("description", "")
    description = re.sub(r'<[^>]+>', ' ', description)
    description = re.sub(r'\s+', ' ', description).strip()

    result = {
        "id": v["id"],
        "name": v["name"],
        "company": v["employer"]["name"],
        "company_url": v["employer"].get("alternate_url"),
        "description": description[:3000],  # Обрезаем для экономии токенов
        "key_skills": [s["name"] for s in v.get("key_skills", [])],
        "experience": v.get("experience", {}).get("name"),
        "employment": v.get("employment", {}).get("name"),
        "schedule": v.get("schedule", {}).get("name"),
        "salary": v.get("salary"),
        "area": v["area"]["name"],
        "url": v["alternate_url"],
        "contacts": v.get("contacts"),
    }

    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool()
def get_my_resumes() -> str:
    """
    Получить список моих резюме (требуется авторизация)

    Returns:
        Список резюме пользователя
    """
    client = get_client()

    if not client.access_token:
        return json.dumps({
            "error": "Не авторизован",
            "instruction": "Выполните: hh-applicant-tool authorize"
        }, ensure_ascii=False)

    try:
        data = client.get("/resumes/mine")
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)

    resumes = []
    for r in data.get("items", []):
        resumes.append({
            "id": r["id"],
            "title": r["title"],
            "status": r.get("status", {}).get("name", "Unknown"),
            "url": r["alternate_url"],
            "total_views": r.get("total_views", 0),
            "new_views": r.get("new_views", 0),
        })

    return json.dumps(resumes, ensure_ascii=False, indent=2)


@mcp.tool()
def get_resume_details(resume_id: str) -> str:
    """
    Получить подробную информацию о резюме

    Args:
        resume_id: ID резюме

    Returns:
        Подробная информация о резюме (для генерации сопроводительных писем)
    """
    client = get_client()

    if not client.access_token:
        return json.dumps({"error": "Не авторизован"}, ensure_ascii=False)

    try:
        r = client.get(f"/resumes/{resume_id}")
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)

    result = {
        "id": r["id"],
        "title": r.get("title"),
        "skills": r.get("skill_set", []),
        "experience": [],
        "total_experience": r.get("total_experience", {}).get("months", 0),
    }

    # Опыт работы
    for exp in r.get("experience", []):
        result["experience"].append({
            "company": exp.get("company"),
            "position": exp.get("position"),
            "description": exp.get("description", "")[:500],
        })

    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool()
def apply_to_vacancy(
    vacancy_id: str,
    resume_id: str,
    message: str | None = None
) -> str:
    """
    Откликнуться на вакансию (требуется авторизация)

    Args:
        vacancy_id: ID вакансии
        resume_id: ID резюме для отклика
        message: Сопроводительное письмо (рекомендуется для повышения шансов)

    Returns:
        Результат отклика
    """
    client = get_client()

    if not client.access_token:
        return json.dumps({
            "error": "Не авторизован",
            "instruction": "Выполните: hh-applicant-tool authorize"
        }, ensure_ascii=False)

    params = {
        "vacancy_id": vacancy_id,
        "resume_id": resume_id,
    }
    if message:
        params["message"] = message

    try:
        client.post("/negotiations", params)
        save_token()  # Сохраняем обновлённый токен
        return json.dumps({
            "success": True,
            "message": f"Успешно откликнулись на вакансию {vacancy_id}"
        }, ensure_ascii=False)
    except Exception as e:
        error_msg = str(e)
        if "already_applied" in error_msg.lower() or "403" in error_msg:
            return json.dumps({
                "success": False,
                "error": "Вы уже откликались на эту вакансию"
            }, ensure_ascii=False)
        return json.dumps({
            "success": False,
            "error": error_msg
        }, ensure_ascii=False)


@mcp.tool()
def update_resume(resume_id: str) -> str:
    """
    Поднять резюме в поиске (требуется авторизация)
    Можно делать раз в 4 часа.

    Args:
        resume_id: ID резюме

    Returns:
        Результат обновления
    """
    client = get_client()

    if not client.access_token:
        return json.dumps({"error": "Не авторизован"}, ensure_ascii=False)

    try:
        client.post(f"/resumes/{resume_id}/publish")
        save_token()
        return json.dumps({
            "success": True,
            "message": f"Резюме {resume_id} поднято в поиске"
        }, ensure_ascii=False)
    except Exception as e:
        error_msg = str(e)
        if "429" in error_msg or "too_early" in error_msg.lower():
            return json.dumps({
                "success": False,
                "error": "Слишком рано. Резюме можно поднимать раз в 4 часа."
            }, ensure_ascii=False)
        return json.dumps({
            "success": False,
            "error": error_msg
        }, ensure_ascii=False)


@mcp.tool()
def edit_resume(
    resume_id: str,
    title: str = None,
    skills: str = None,
    salary: int = None,
) -> str:
    """
    Редактировать резюме (заголовок, навыки, зарплата)

    Args:
        resume_id: ID резюме
        title: Новый заголовок резюме (желаемая должность)
        skills: Навыки через запятую (например: "Python, FastAPI, Docker")
        salary: Желаемая зарплата в рублях (например: 100000)

    Returns:
        Результат редактирования
    """
    client = get_client()

    if not client.access_token:
        return json.dumps({"error": "Не авторизован"}, ensure_ascii=False)

    # Собираем данные для обновления
    update_data = {}

    if title:
        update_data["title"] = title

    if skills:
        # Преобразуем строку навыков в список словарей
        skill_list = [s.strip() for s in skills.split(",") if s.strip()]
        update_data["skill_set"] = skill_list

    if salary:
        update_data["salary"] = {"amount": salary, "currency": "RUR"}

    if not update_data:
        return json.dumps({
            "success": False,
            "error": "Не указаны данные для обновления"
        }, ensure_ascii=False)

    try:
        client.put(f"/resumes/{resume_id}", update_data, as_json=True)
        save_token()
        return json.dumps({
            "success": True,
            "message": f"Резюме обновлено",
            "updated_fields": list(update_data.keys())
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": str(e)
        }, ensure_ascii=False)


@mcp.tool()
def get_negotiations() -> str:
    """
    Получить список откликов и приглашений

    Returns:
        Список активных откликов
    """
    client = get_client()

    if not client.access_token:
        return json.dumps({"error": "Не авторизован"}, ensure_ascii=False)

    try:
        data = client.get("/negotiations")
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)

    negotiations = []
    for n in data.get("items", []):
        vacancy = n.get("vacancy", {})
        negotiations.append({
            "id": n["id"],
            "state": n.get("state", {}).get("name"),
            "vacancy_id": vacancy.get("id"),
            "vacancy_name": vacancy.get("name"),
            "company": vacancy.get("employer", {}).get("name"),
            "created_at": n.get("created_at"),
            "has_updates": n.get("has_updates", False),
        })

    return json.dumps({
        "total": len(negotiations),
        "negotiations": negotiations
    }, ensure_ascii=False, indent=2)


@mcp.tool()
def get_portfolio_projects(relevance: str | None = None) -> str:
    """
    Получить информацию о проектах кандидата из PORTFOLIO.md файлов

    Args:
        relevance: Фильтр по релевантности (high, medium, low). По умолчанию все.

    Returns:
        Список проектов с описанием, стеком и готовыми фразами для резюме
    """
    import glob

    profile = load_profile()
    if not profile or not profile.get("projects_path"):
        return json.dumps({
            "error": "projects_path не указан в profile.json",
            "instruction": "Добавьте projects_path в profile.json"
        }, ensure_ascii=False)

    dev_path = profile["projects_path"]
    pattern = os.path.join(dev_path, "*", "PORTFOLIO.md")

    projects = []
    for filepath in glob.glob(pattern):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()

            # Парсим relevance из frontmatter
            project_relevance = "medium"
            if "relevance:" in content:
                for line in content.split("\n"):
                    if line.startswith("relevance:"):
                        project_relevance = line.split(":")[1].strip()
                        break

            # Фильтруем по relevance если указан
            if relevance and project_relevance != relevance:
                continue

            project_name = os.path.basename(os.path.dirname(filepath))
            projects.append({
                "project": project_name,
                "relevance": project_relevance,
                "content": content[:2000]  # Ограничиваем размер
            })
        except Exception as e:
            continue

    if not projects:
        return json.dumps({
            "error": "PORTFOLIO.md файлы не найдены",
            "instruction": "Создайте PORTFOLIO.md в папках проектов с помощью Kimi Code"
        }, ensure_ascii=False)

    # Сортируем: high первые
    priority = {"high": 0, "medium": 1, "low": 2}
    projects.sort(key=lambda x: priority.get(x["relevance"], 1))

    return json.dumps({
        "total": len(projects),
        "projects": projects
    }, ensure_ascii=False, indent=2)


@mcp.tool()
def get_candidate_profile() -> str:
    """
    Получить профиль кандидата для генерации сопроводительных писем

    Returns:
        Базовая информация, навыки, позиционирование и шаблон письма
    """
    profile = load_profile()

    if not profile:
        return json.dumps({
            "error": "profile.json не найден",
            "instruction": "Скопируйте profile.example.json в profile.json и заполните свои данные"
        }, ensure_ascii=False, indent=2)

    return json.dumps(profile, ensure_ascii=False, indent=2)


@mcp.tool()
def get_areas() -> str:
    """
    Получить список популярных регионов для поиска

    Returns:
        Словарь регионов с ID
    """
    areas = {
        "113": "Россия (вся)",
        "1": "Москва",
        "2": "Санкт-Петербург",
        "1001": "Москва и МО",
        "2019": "Новосибирск",
        "88": "Казань",
        "66": "Нижний Новгород",
        "3": "Екатеринбург",
        "54": "Красноярск",
        "104": "Краснодар",
        "68": "Самара",
        "76": "Ростов-на-Дону",
        "4": "Новосибирская область",
    }
    return json.dumps(areas, ensure_ascii=False, indent=2)


@mcp.tool()
def get_dictionaries() -> str:
    """
    Получить справочники (опыт, тип занятости, график)

    Returns:
        Справочники для фильтрации вакансий
    """
    dictionaries = {
        "experience": {
            "noExperience": "Нет опыта",
            "between1And3": "От 1 до 3 лет",
            "between3And6": "От 3 до 6 лет",
            "moreThan6": "Более 6 лет",
        },
        "employment": {
            "full": "Полная занятость",
            "part": "Частичная занятость",
            "project": "Проектная работа",
            "volunteer": "Волонтёрство",
            "probation": "Стажировка",
        },
        "schedule": {
            "fullDay": "Полный день",
            "shift": "Сменный график",
            "flexible": "Гибкий график",
            "remote": "Удалённая работа",
            "flyInFlyOut": "Вахтовый метод",
        }
    }
    return json.dumps(dictionaries, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    mcp.run()

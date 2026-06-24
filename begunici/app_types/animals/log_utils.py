import json
import re


HTTP_STATUS_RE = re.compile(r"\s*;?\s*HTTP\s+(?P<status>\d{3})\s*", re.IGNORECASE)
RAW_REQUEST_RE = re.compile(
    r"^(?P<method>GET|POST|PUT|PATCH|DELETE)\s+запрос к\s+(?P<path>/[^\s;]+)",
    re.IGNORECASE,
)


ANIMAL_OBJECT_TYPES = {
    "Производитель",
    "Баран-Производитель",
    "Баран",
    "Баранчик",
    "Ярка",
    "Овца",
    "Овцематка",
}

TAG_LINK_OBJECT_TYPES = ANIMAL_OBJECT_TYPES | {
    "Ветеринарная обработка",
    "Запись о весе",
    "Окот",
}


def strip_http_status(value):
    if value is None:
        return ""
    return HTTP_STATUS_RE.sub("", str(value)).strip(" ;")


def parse_status_code(*values):
    for value in values:
        if value in (None, ""):
            continue
        try:
            return int(value)
        except (TypeError, ValueError):
            match = HTTP_STATUS_RE.search(str(value))
            if match:
                return int(match.group("status"))
    return None


def parse_json_details(raw_details):
    if not raw_details:
        return None
    try:
        parsed = json.loads(raw_details)
    except (TypeError, ValueError):
        return None
    return parsed if isinstance(parsed, dict) else None


def _normalize_path(path):
    path = (path or "").split("?", 1)[0].strip()
    if path and not path.startswith("/"):
        path = "/" + path
    return path


def _failure_prefix(action, status_code):
    if status_code and int(status_code) >= 400:
        return f"Ошибка: {action}"
    return action


def _params_get(params, key):
    if not isinstance(params, dict):
        return None
    value = params.get(key)
    if isinstance(value, (list, tuple)):
        return value[0] if value else None
    return value


def resolve_log_action(method, path, params=None, status_code=None):
    method = (method or "").upper()
    path = _normalize_path(path)
    params = params or {}

    action = None

    if "/backup/" in path:
        if method == "POST" and "/create/" in path:
            action = "Создание резервной копии"
        elif method == "POST" and "/restore/" in path:
            action = "Восстановление из резервной копии"
        elif method == "DELETE":
            action = "Удаление резервной копии"

    elif "/animals/notes/" in path:
        if method == "POST":
            action = "Создание заметки календаря"
        elif method in {"PUT", "PATCH"}:
            action = "Редактирование заметки календаря"
        elif method == "DELETE":
            action = "Удаление заметки календаря"

    elif "/animals/journals/shift-transfer/" in path and method == "POST":
        journal_action = _params_get(params, "action") or _params_get(
            params, "journal_action"
        )
        if journal_action == "create":
            action = "Создание заметки передачи смены"
        elif journal_action == "update":
            action = "Редактирование заметки передачи смены"
        else:
            action = "Изменение заметки передачи смены"

    elif "/animals/" in path:
        if method == "GET" and "/api/otbivka/export-excel/" in path:
            action = "Экспорт отбивки в Excel"
        elif method == "GET" and "/api/vet-list/export-excel/" in path:
            action = "Экспорт ветобработок в Excel"
        elif method == "GET" and "/api/lambings/export-excel/" in path:
            action = "Экспорт случек в Excel"
        elif method == "GET" and "/api/lambing-groups/export-excel/" in path:
            action = "Экспорт групп случек в Excel"
        elif method == "GET" and "/api/archive/export-excel/" in path:
            action = "Экспорт архива в Excel"
        elif method == "GET" and "/api/archive/act/" in path:
            action = "Скачивание акта архивации"
        elif method == "GET" and "/api/export-excel/" in path:
            action = "Экспорт списка животных в Excel"
        elif method == "POST" and "/api/archive/act-preview/" in path:
            action = "Предпросмотр акта архивации"
        elif method == "POST" and "/api/check-kinship/" in path:
            action = "Проверка родства"
        elif method == "POST" and "/api/kinship-pairs/export-excel/" in path:
            action = "Экспорт подбора пар в Excel"
        elif method == "POST" and "/api/export-excel/" in path:
            action = "Экспорт списка животных в Excel"
        elif method == "POST" and "/api/otbivka/export-excel/" in path:
            action = "Экспорт отбивки в Excel"
        elif method == "POST" and "/api/vet-list/export-excel/" in path:
            action = "Экспорт ветобработок в Excel"
        elif method == "POST" and "/api/lambings/export-excel/" in path:
            action = "Экспорт случек в Excel"
        elif method == "POST" and "/api/lambing-groups/export-excel/" in path:
            action = "Экспорт групп случек в Excel"
        elif method == "POST" and "/api/archive/export-excel/" in path:
            action = "Экспорт архива в Excel"
        elif method == "POST" and "/api/bulk-otbivka/" in path:
            action = "Массовая отбивка"
        elif method == "POST" and "/api/bulk-vaccination/" in path:
            action = "Ковровая ветобработка"
        elif method == "POST" and "/api/bulk-create-lambings/" in path:
            action = "Массовое создание окотов"
        elif method == "POST" and "/actions/bulk_archive/" in path:
            action = "Массовый перенос в архив"
        elif method == "POST" and "/lambing-group/" in path and "/remove-father/" in path:
            action = "Снятие барана из группы"
        elif method == "POST" and path.rstrip("/") == "/animals/lambing-group":
            action = "Постановка в группу"
        elif method == "POST" and "/to_maker/" in path:
            action = "Преобразование баранчика в барана-производителя"
        elif method == "POST" and "/to_sheep/" in path:
            action = "Преобразование ярки в овцематку"
        elif method == "POST" and "/hide_vet_treatment/" in path:
            action = "Скрытие ветобработки"
        elif method == "POST" and "/add_place_movement/" in path:
            action = "Добавление перемещения"
        elif method == "POST" and "/update_working_condition/" in path:
            action = "Обновление рабочего состояния"
        elif method == "POST" and "/add_weight/" in path:
            action = "Добавление записи о весе"
        elif method == "POST" and "/add_vet_care/" in path:
            action = "Добавление ветобработки"
        elif method == "POST" and "/add_lambing/" in path:
            action = "Создание окота"
        elif method == "POST" and "/complete-early-failure/" in path:
            action = "Досрочное завершение окота"
        elif method == "POST" and "/complete-with-children/" in path:
            action = "Завершение окота с детьми"
        elif method == "POST" and "/complete/" in path:
            action = "Завершение окота"
        elif method == "POST" and "/lambing/" in path:
            action = "Создание окота"
        elif method in {"PUT", "PATCH"} and "/lambing/" in path:
            action = "Редактирование окота"
        elif method == "DELETE" and "/lambing/" in path:
            action = "Удаление окота"
        elif method in {"PUT", "PATCH"}:
            if "/archive/" in path:
                action = "Перенос в архив"
            elif "/restore/" in path:
                action = "Восстановление из архива"
            elif "/move/" in path:
                action = "Перемещение животного"
            elif "/update/" in path or re.search(r"/animals/(maker|ram|ewe|sheep)/", path):
                action = "Редактирование животного"
            else:
                action = "Обновление данных"
        elif method == "DELETE":
            action = "Удаление животного"
        elif method == "GET" and (
            _params_get(params, "export") == "1" or "/export-detail-excel/" in path
        ):
            if "/journals/progeny/" in path:
                action = "Экспорт журнала Приплод"
            elif "/journals/insemination/" in path:
                action = "Экспорт журнала Осеменение"
            elif "/journals/three/" in path:
                action = "Экспорт журнала Выбытие"
            elif "/journals/shift-transfer/" in path:
                action = "Экспорт журнала Передача смены"
            elif "/export-detail-excel/" in path:
                action = "Экспорт карточки животного в Excel"
            else:
                action = "Экспорт данных"

    elif "/veterinary/" in path:
        if method == "POST" and "/api/care/" in path:
            action = "Создание ветобработки"
        elif method == "POST" and "/api/place/" in path:
            action = "Создание овчарни"
        elif method == "POST" and "/api/status/" in path:
            action = "Создание статуса"
        elif method == "POST" and "/api/veterinary/" in path:
            action = "Добавление ветобработки животному"
        elif method == "POST" and "/api/weight-record/" in path:
            action = "Добавление записи о весе"
        elif method == "POST" and "/api/place_movement/" in path:
            action = "Добавление перемещения"
        elif method == "POST" and "/api/tag/" in path:
            action = "Создание бирки"
        elif method in {"PUT", "PATCH"} and "/api/care/" in path:
            action = "Редактирование ветобработки"
        elif method in {"PUT", "PATCH"} and "/api/place/" in path:
            action = "Редактирование овчарни"
        elif method in {"PUT", "PATCH"} and "/api/status/" in path:
            action = "Редактирование статуса"
        elif method in {"PUT", "PATCH"} and "/api/veterinary/" in path:
            action = "Редактирование ветобработки животного"
        elif method in {"PUT", "PATCH"} and "/api/weight-record/" in path:
            action = "Редактирование записи о весе"
        elif method in {"PUT", "PATCH"} and "/api/place_movement/" in path:
            action = "Редактирование перемещения"
        elif method in {"PUT", "PATCH"} and "/api/tag/" in path:
            action = "Редактирование бирки"
        elif method == "DELETE" and "/api/care/" in path:
            action = "Удаление ветобработки"
        elif method == "DELETE" and "/api/place/" in path:
            action = "Удаление овчарни"
        elif method == "DELETE" and "/api/status/" in path:
            action = "Удаление статуса"
        elif method == "DELETE" and "/api/veterinary/" in path:
            action = "Удаление ветобработки животного"
        elif method == "DELETE" and "/api/weight-record/" in path:
            action = "Удаление записи о весе"
        elif method == "DELETE" and "/api/place_movement/" in path:
            action = "Удаление перемещения"
        elif method == "DELETE" and "/api/tag/" in path:
            action = "Удаление бирки"
        elif method == "GET" and "/api/export-cares/" in path:
            action = "Экспорт ветобработок в Excel"

    if not action:
        action = f"{method} запрос к {path}".strip()

    return _failure_prefix(action, status_code)


def resolve_log_object_type(method, path):
    path = _normalize_path(path)

    if "/backup/" in path:
        return "Резервная копия"
    if "/animals/notes/" in path:
        return "Заметка календаря"
    if "/animals/journals/shift-transfer/" in path:
        return "Передача смены"
    if "/animals/lambing-group/" in path:
        return "Группа случки"
    if "/api/check-kinship/" in path or "/api/kinship-pairs/" in path:
        return "Подбор пар"
    if "/api/bulk-otbivka/" in path:
        return "Отбивка"
    if "/api/bulk-vaccination/" in path:
        return "Ветобработка"
    if "/api/lambings/" in path or "/lambing/" in path:
        return "Окот"
    if (
        "/api/archive/" in path
        or "/main_archive/" in path
        or "/actions/bulk_archive/" in path
    ):
        return "Архив"
    if "/api/export-excel/" in path:
        return "Список животных"
    if "/api/otbivka/" in path or "/otbivka/" in path:
        return "Отбивка"
    if "/api/vet-list/" in path or "/vet-list/" in path:
        return "Ветобработка"
    if "/maker/" in path:
        return "Баран-Производитель"
    if "/ram/" in path:
        return "Баранчик"
    if "/ewe/" in path:
        return "Ярка"
    if "/sheep/" in path:
        return "Овцематка"
    if "/veterinary/api/weight-record/" in path:
        return "Запись о весе"
    if "/veterinary/api/place_movement/" in path:
        return "Перемещение"
    if "/veterinary/api/veterinary/" in path:
        return "Ветеринарная обработка"
    if "/veterinary/api/tag/" in path:
        return "Бирка"
    if "/veterinary/api/care/" in path or "/veterinary/cares/" in path:
        return "Ветобработка"
    if "/veterinary/api/place/" in path or "/veterinary/places/" in path:
        return "Овчарня"
    if "/veterinary/api/status/" in path or "/veterinary/statuses/" in path:
        return "Статус"
    return "Неизвестно"


def resolve_log_object_id(method, path):
    path = _normalize_path(path)
    path_parts = [part for part in path.strip("/").split("/") if part]

    archive_act_match = re.search(r"/animals/api/archive/act/[^/]+/([^/]+)/?", path)
    if archive_act_match:
        return archive_act_match.group(1)

    group_match = re.search(r"/animals/lambing-group/(\d+)/", path)
    if group_match:
        return group_match.group(1)

    lambing_match = re.search(r"/animals/lambing/(\d+)/", path)
    if lambing_match:
        return lambing_match.group(1)

    if "/animals/" in path and "/notes/" not in path:
        for i, part in enumerate(path_parts):
            if part in {"maker", "ram", "ewe", "sheep"} and i + 1 < len(path_parts):
                return path_parts[i + 1]

    if "/animals/notes/" in path or "/veterinary/" in path:
        return ""

    for part in path_parts:
        if part.isdigit():
            return part

    return ""


def extract_request_context(action_type, raw_details, parsed_details, additional_data):
    method = None
    path = None
    status_code = None
    params = {}

    if isinstance(parsed_details, dict):
        method = parsed_details.get("method")
        path = parsed_details.get("path")
        status_code = parse_status_code(parsed_details.get("status_code"))

        if isinstance(parsed_details.get("params"), dict):
            params.update(parsed_details.get("params") or {})
        if parsed_details.get("journal_action"):
            params["journal_action"] = parsed_details.get("journal_action")

        nested = parsed_details.get("additional_data")
        if isinstance(nested, dict):
            method = nested.get("method") or method
            path = nested.get("path") or path
            status_code = parse_status_code(nested.get("status_code"), status_code)

    if isinstance(additional_data, dict):
        method = additional_data.get("method") or method
        path = additional_data.get("path") or path
        status_code = parse_status_code(additional_data.get("status_code"), status_code)

    for value in (action_type, raw_details):
        if method and path:
            break
        match = RAW_REQUEST_RE.search(str(value or ""))
        if match:
            method = match.group("method").upper()
            path = match.group("path")

    status_code = parse_status_code(status_code, action_type, raw_details)
    return method, _normalize_path(path), status_code, params


def is_raw_request_label(value):
    return bool(RAW_REQUEST_RE.search(str(value or "")))


def format_log_details(raw_details, parsed_details, fallback_action, status_code=None):
    if isinstance(parsed_details, dict):
        details_text = str(parsed_details.get("action") or fallback_action or "")
        if is_raw_request_label(details_text):
            details_text = fallback_action

        if parsed_details.get("type"):
            details_text += f" ({parsed_details['type']})"

        changed_fields = parsed_details.get("changed_fields")
        if isinstance(changed_fields, list) and changed_fields:
            details_text += f"; поля: {', '.join(str(field) for field in changed_fields)}"
    else:
        details_text = strip_http_status(raw_details)
        if not details_text or is_raw_request_label(details_text):
            details_text = fallback_action or ""

    details_text = strip_http_status(details_text)

    if status_code and int(status_code) >= 400 and "не выполнено" not in details_text.lower():
        details_text = f"{details_text}; результат: не выполнено"

    return details_text or fallback_action or ""


def normalize_log_for_display(log):
    raw_details = log.description or ""
    parsed_details = parse_json_details(raw_details)
    method, path, status_code, params = extract_request_context(
        log.action_type,
        raw_details,
        parsed_details,
        log.additional_data,
    )

    display_action = strip_http_status(log.action_type)
    display_object_type = strip_http_status(log.object_type)
    display_object_id = log.object_id or ""

    if method and path:
        normalized_action = resolve_log_action(
            method,
            path,
            params=params,
            status_code=status_code,
        )
        is_middleware_details = (
            isinstance(parsed_details, dict)
            and parsed_details.get("method")
            and parsed_details.get("path")
        )
        if (
            not display_action
            or is_raw_request_label(display_action)
            or is_middleware_details
        ):
            display_action = normalized_action

        if not display_object_type or display_object_type == "Неизвестно":
            display_object_type = resolve_log_object_type(method, path)

        resolved_object_id = resolve_log_object_id(method, path)
        if (
            resolved_object_id
            and (
                not display_object_id
                or display_object_type in {"Группа случки", "Окот", "Архив"}
                or is_raw_request_label(log.action_type)
            )
        ):
            display_object_id = resolved_object_id

        details_source = parsed_details
        if is_middleware_details:
            details_source = dict(parsed_details)
            details_source["action"] = normalized_action

        details_text = format_log_details(
            raw_details,
            details_source,
            fallback_action=normalized_action,
            status_code=status_code,
        )
    else:
        details_text = format_log_details(
            raw_details,
            parsed_details,
            fallback_action=display_action,
            status_code=status_code,
        )

    if not display_action:
        display_action = "Действие"
    if not display_object_type:
        display_object_type = "-"

    return {
        "action": display_action,
        "object_type": display_object_type,
        "object_id": display_object_id,
        "details": details_text,
        "method": method,
        "path": path,
        "status_code": status_code,
    }

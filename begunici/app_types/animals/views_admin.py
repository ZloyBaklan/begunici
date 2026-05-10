import json
from datetime import datetime

import pytz
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import render

from .models_user_log import UserActionLog


def _has_admin_panel_access(user):
    return user.groups.filter(name__in=["Admin", "Main"]).exists()


def _resolve_log_action(method, path, params=None):
    method = (method or "").upper()
    path = path or ""
    params = params or {}

    if "/backup/" in path:
        if method == "POST" and "/create/" in path:
            return "Создание резервной копии"
        if method == "POST" and "/restore/" in path:
            return "Восстановление из резервной копии"
        if method == "DELETE":
            return "Удаление резервной копии"

    if "/animals/notes/" in path:
        if method == "POST":
            return "Создание заметки календаря"
        if method in {"PUT", "PATCH"}:
            return "Редактирование заметки календаря"
        if method == "DELETE":
            return "Удаление заметки календаря"

    if "/animals/journals/shift-transfer/" in path and method == "POST":
        journal_action = params.get("action")
        if journal_action == "create":
            return "Создание заметки передачи смены"
        if journal_action == "update":
            return "Редактирование заметки передачи смены"
        return "Изменение заметки передачи смены"

    if "/animals/" in path:
        if method == "GET" and "/api/otbivka/export-excel/" in path:
            return "Экспорт отбивки в Excel"
        if method == "GET" and "/api/vet-list/export-excel/" in path:
            return "Экспорт ветобработок в Excel"
        if method == "GET" and "/api/lambings/export-excel/" in path:
            return "Экспорт окотов в Excel"
        if method == "GET" and "/api/archive/export-excel/" in path:
            return "Экспорт архива в Excel"
        if method == "GET" and "/api/export-excel/" in path:
            return "Экспорт списка животных в Excel"
        if method == "POST" and "/api/check-kinship/" in path:
            return "Проверка родства"
        if method == "POST" and "/api/kinship-pairs/export-excel/" in path:
            return "Экспорт подбора пар в Excel"
        if method == "POST" and "/api/export-excel/" in path:
            return "Экспорт списка животных в Excel"
        if method == "POST" and "/api/otbivka/export-excel/" in path:
            return "Экспорт отбивки в Excel"
        if method == "POST" and "/api/vet-list/export-excel/" in path:
            return "Экспорт ветобработок в Excel"
        if method == "POST" and "/api/lambings/export-excel/" in path:
            return "Экспорт окотов в Excel"
        if method == "POST" and "/api/archive/export-excel/" in path:
            return "Экспорт архива в Excel"
        if method == "POST" and "/api/bulk-otbivka/" in path:
            return "Массовая отбивка"
        if method == "POST" and "/api/bulk-vaccination/" in path:
            return "Ковровая ветобработка"
        if method == "POST" and "/to_maker/" in path:
            return "Преобразование баранчика в барана-производителя"
        if method == "POST" and "/to_sheep/" in path:
            return "Преобразование ярки в овцематку"
        if method == "POST" and "/hide_vet_treatment/" in path:
            return "Скрытие ветобработки"
        if method == "POST" and "/add_place_movement/" in path:
            return "Добавление перемещения"
        if method == "POST" and "/update_working_condition/" in path:
            return "Обновление рабочего состояния"
        if method == "POST" and "/add_weight/" in path:
            return "Добавление записи о весе"
        if method == "POST" and "/add_vet_care/" in path:
            return "Добавление ветобработки"
        if method == "POST" and "/add_lambing/" in path:
            return "Создание окота"
        if method == "POST" and "/lambing/" in path:
            return "Создание окота"
        if method in {"PUT", "PATCH"} and "/lambing/" in path:
            return "Редактирование окота"
        if method == "DELETE" and "/lambing/" in path:
            return "Удаление окота"
        if method in {"PUT", "PATCH"}:
            if "/archive/" in path:
                return "Перенос в архив"
            if "/restore/" in path:
                return "Восстановление из архива"
            if "/move/" in path:
                return "Перемещение животного"
            if "/update/" in path:
                return "Редактирование животного"
            return "Обновление данных"
        if method == "DELETE":
            return "Удаление животного"
        if method == "GET" and (
            params.get("export") == "1" or "/export-detail-excel/" in path
        ):
            if "/journals/progeny/" in path:
                return "Экспорт журнала Приплод"
            if "/journals/insemination/" in path:
                return "Экспорт журнала Осеменение"
            if "/journals/three/" in path:
                return "Экспорт Журнала 3"
            if "/journals/shift-transfer/" in path:
                return "Экспорт журнала Передача смены"
            if "/export-detail-excel/" in path:
                return "Экспорт карточки животного в Excel"
            return "Экспорт данных"

    if "/veterinary/" in path:
        if method == "POST" and "/api/care/" in path:
            return "Создание ветобработки"
        if method == "POST" and "/api/place/" in path:
            return "Создание овчарни"
        if method == "POST" and "/api/status/" in path:
            return "Создание статуса"
        if method in {"PUT", "PATCH"} and "/api/care/" in path:
            return "Редактирование ветобработки"
        if method in {"PUT", "PATCH"} and "/api/place/" in path:
            return "Редактирование овчарни"
        if method in {"PUT", "PATCH"} and "/api/status/" in path:
            return "Редактирование статуса"
        if method == "DELETE" and "/api/care/" in path:
            return "Удаление ветобработки"
        if method == "DELETE" and "/api/place/" in path:
            return "Удаление овчарни"
        if method == "DELETE" and "/api/status/" in path:
            return "Удаление статуса"
        if method == "GET" and "/api/export-cares/" in path:
            return "Экспорт ветобработок в Excel"

    return f"{method} запрос к {path}".strip()


def _resolve_log_object_type(path):
    path = path or ""

    if "/backup/" in path:
        return "Резервная копия"
    if "/animals/notes/" in path:
        return "Заметка календаря"
    if "/animals/journals/shift-transfer/" in path:
        return "Передача смены"
    if "/api/check-kinship/" in path or "/api/kinship-pairs/" in path:
        return "Подбор пар"
    if "/api/bulk-otbivka/" in path:
        return "Отбивка"
    if "/api/bulk-vaccination/" in path:
        return "Ветобработка"
    if "/api/lambings/" in path or "/lambing/" in path:
        return "Окот"
    if "/api/archive/" in path or "/main_archive/" in path:
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
    if "/veterinary/api/care/" in path or "/veterinary/cares/" in path:
        return "Ветобработка"
    if "/veterinary/api/place/" in path or "/veterinary/places/" in path:
        return "Овчарня"
    if "/veterinary/api/status/" in path or "/veterinary/statuses/" in path:
        return "Статус"
    return "Неизвестно"


def _format_details_text(raw_details, parsed_details, fallback_action):
    if not isinstance(parsed_details, dict):
        return raw_details or ""

    if parsed_details.get("action"):
        details_text = str(parsed_details["action"])
        if parsed_details.get("type"):
            details_text += f" ({parsed_details['type']})"
    else:
        details_text = fallback_action

    changed_fields = parsed_details.get("changed_fields")
    if isinstance(changed_fields, list) and changed_fields:
        details_text += f"; Поля: {', '.join(str(field) for field in changed_fields)}"

    status_code = parsed_details.get("status_code")
    if status_code:
        details_text += f"; HTTP {status_code}"

    return details_text


@login_required
def admin_panel(request):
    """Панель администратора для просмотра логов действий."""
    if not _has_admin_panel_access(request.user):
        return render(
            request,
            "error.html",
            {"error_message": "У вас нет прав доступа к панели администратора"},
        )

    return render(request, "admin_panel.html")


@login_required
def admin_logs_api(request):
    """API для получения логов действий пользователей."""
    try:
        if not _has_admin_panel_access(request.user):
            return JsonResponse({"error": "Нет прав доступа"}, status=403)

        page = int(request.GET.get("page", 1))
        search = request.GET.get("search", "")
        user_filter = request.GET.get("user", "")
        date_filter = request.GET.get("date", "")

        logs = UserActionLog.objects.select_related("user").order_by("-timestamp")

        if search:
            logs = logs.filter(
                Q(action_type__icontains=search)
                | Q(object_type__icontains=search)
                | Q(description__icontains=search)
            )

        if user_filter:
            logs = logs.filter(user__username__icontains=user_filter)

        if date_filter:
            try:
                filter_date = datetime.strptime(date_filter, "%Y-%m-%d").date()
                logs = logs.filter(timestamp__date=filter_date)
            except ValueError:
                pass

        paginator = Paginator(logs, 50)
        page_obj = paginator.get_page(page)

        moscow_tz = pytz.timezone("Europe/Moscow")
        logs_data = []

        for log in page_obj:
            moscow_time = log.timestamp.astimezone(moscow_tz)

            animal_link_info = None
            if log.object_id:
                from begunici.app_types.animals.models import Ewe, Maker, Ram, Sheep

                if ", " in log.object_id:
                    tags = [tag.strip() for tag in log.object_id.split(", ")]
                    if len(tags) == 2:
                        animal_link_info = {"pair_tags": []}
                        animal_types = [
                            (Maker, "maker", "Баран-Производитель"),
                            (Ram, "ram", "Баранчик"),
                            (Ewe, "ewe", "Ярка"),
                            (Sheep, "sheep", "Овцематка"),
                        ]
                        for tag in tags:
                            tag_info = None
                            for model_class, url_type, russian_name in animal_types:
                                try:
                                    if model_class.objects.filter(
                                        tag__tag_number=tag
                                    ).exists():
                                        tag_info = {
                                            "tag": tag,
                                            "url_type": url_type,
                                            "russian_name": russian_name,
                                        }
                                        break
                                except Exception:
                                    continue
                            if tag_info:
                                animal_link_info["pair_tags"].append(tag_info)
                            else:
                                animal_link_info["pair_tags"].append(
                                    {"tag": tag, "url_type": None}
                                )
                else:
                    animal_types = [
                        (Maker, "maker", "Баран-Производитель"),
                        (Ram, "ram", "Баранчик"),
                        (Ewe, "ewe", "Ярка"),
                        (Sheep, "sheep", "Овцематка"),
                    ]
                    for model_class, url_type, russian_name in animal_types:
                        try:
                            if model_class.objects.filter(
                                tag__tag_number=log.object_id
                            ).exists():
                                animal_link_info = {
                                    "url_type": url_type,
                                    "russian_name": russian_name,
                                }
                                break
                        except Exception:
                            continue

            parsed_details = None
            raw_details = log.description or ""
            try:
                parsed_details = json.loads(raw_details) if raw_details else None
            except (TypeError, ValueError):
                parsed_details = None

            display_action = log.action_type or ""
            display_object_type = log.object_type or ""

            method = None
            path = None
            params = {}
            if isinstance(parsed_details, dict):
                method = parsed_details.get("method")
                path = parsed_details.get("path")
                if isinstance(parsed_details.get("params"), dict):
                    params = parsed_details.get("params") or {}
                if isinstance(parsed_details.get("additional_data"), dict):
                    maybe_method = parsed_details["additional_data"].get("method")
                    maybe_path = parsed_details["additional_data"].get("path")
                    if maybe_method and maybe_path:
                        method = maybe_method
                        path = maybe_path

            if method and path:
                normalized_action = _resolve_log_action(method, path, params=params)
                if not display_action or display_action.startswith(f"{str(method).upper()} запрос к"):
                    display_action = normalized_action
                if not display_object_type or display_object_type == "Неизвестно":
                    display_object_type = _resolve_log_object_type(path)
                details_text = _format_details_text(
                    raw_details=raw_details,
                    parsed_details=parsed_details,
                    fallback_action=normalized_action,
                )
            else:
                details_text = _format_details_text(
                    raw_details=raw_details,
                    parsed_details=parsed_details,
                    fallback_action=display_action,
                )

            if not display_action:
                display_action = "Действие"
            if not display_object_type:
                display_object_type = "-"

            logs_data.append(
                {
                    "id": log.id,
                    "user": log.user.username,
                    "action": display_action,
                    "object_type": display_object_type,
                    "object_id": log.object_id or "",
                    "details": details_text,
                    "timestamp": moscow_time.strftime("%d.%m.%Y %H:%M:%S"),
                    "animal_link_info": animal_link_info,
                }
            )

        return JsonResponse(
            {
                "logs": logs_data,
                "has_next": page_obj.has_next(),
                "has_previous": page_obj.has_previous(),
                "current_page": page,
                "total_pages": paginator.num_pages,
                "total_count": paginator.count,
            }
        )
    except Exception as e:
        return JsonResponse({"error": f"Ошибка сервера: {str(e)}"}, status=500)


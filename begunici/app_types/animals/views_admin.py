from datetime import datetime

import pytz
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import render

from .log_utils import TAG_LINK_OBJECT_TYPES, normalize_log_for_display
from .models_user_log import UserActionLog


def _has_admin_panel_access(user):
    return user.groups.filter(name__in=["Admin", "Main"]).exists()


def _hide_technical_and_duplicate_logs(logs):
    hidden_preview_logs = (
        Q(action_type__icontains="Предпросмотр акта")
        | Q(description__icontains="/animals/api/archive/act-preview/")
        | Q(additional_data__path="/animals/api/archive/act-preview/")
    )
    successful_middleware_duplicates = Q(additional_data__status_code__lt=400) & (
        Q(additional_data__path="/animals/lambing-group/")
        | Q(additional_data__path__regex=r"^/animals/lambing-group/[0-9]+/remove-father/$")
        | Q(additional_data__path__regex=r"^/animals/lambing/[0-9]+/(complete|complete-with-children|complete-early-failure)/$")
    )
    return logs.exclude(hidden_preview_logs | successful_middleware_duplicates)


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
        logs = _hide_technical_and_duplicate_logs(logs)

        if search:
            logs = logs.filter(
                Q(action_type__icontains=search)
                | Q(object_type__icontains=search)
                | Q(object_id__icontains=search)
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
            display_data = normalize_log_for_display(log)

            display_action = display_data["action"]
            display_object_type = display_data["object_type"]
            display_object_id = display_data["object_id"]
            details_text = display_data["details"]

            animal_link_info = None
            should_build_animal_link = (
                display_object_id
                and display_object_type in TAG_LINK_OBJECT_TYPES
                and (display_object_type != "Окот" or ", " in display_object_id)
            )
            if should_build_animal_link:
                from begunici.app_types.animals.models import Ewe, Maker, Ram, Sheep

                if ", " in display_object_id:
                    tags = [tag.strip() for tag in display_object_id.split(", ")]
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
                                tag__tag_number=display_object_id
                            ).exists():
                                animal_link_info = {
                                    "url_type": url_type,
                                    "russian_name": russian_name,
                                }
                                break
                        except Exception:
                            continue

            logs_data.append(
                {
                    "id": log.id,
                    "user": log.user.username,
                    "action": display_action,
                    "object_type": display_object_type,
                    "object_id": display_object_id,
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


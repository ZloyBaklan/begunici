import json

from django.contrib.auth.models import AnonymousUser
from django.utils.deprecation import MiddlewareMixin

from .models_user_log import UserActionLog


class UserActionLogMiddleware(MiddlewareMixin):
    """Middleware for user activity logging."""

    MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
    IGNORED_PREFIXES = ("/static/", "/admin/", "/login/")
    TECHNICAL_PATH_PARTS = (
        "/backup/check-auto/",
        "/api/health/",
        "/favicon.ico",
        "/robots.txt",
    )

    def process_response(self, request, response):
        if not self._should_log_request(request):
            return response

        action = self.determine_action(request)
        if not action:
            return response

        details = self.get_request_details(request, response, action)

        action_max_len = UserActionLog._meta.get_field("action_type").max_length or 50
        object_type_max_len = (
            UserActionLog._meta.get_field("object_type").max_length or 50
        )
        object_id_max_len = UserActionLog._meta.get_field("object_id").max_length or 100

        UserActionLog.objects.create(
            user=request.user,
            action_type=self._truncate(action, action_max_len),
            object_type=self._truncate(self.get_object_type(request), object_type_max_len),
            object_id=self._truncate(self.get_object_id(request), object_id_max_len),
            description=details,
            additional_data={
                "method": request.method,
                "path": request.path,
                "status_code": response.status_code,
            },
        )

        return response

    def _should_log_request(self, request):
        if isinstance(request.user, AnonymousUser):
            return False

        if request.path.startswith(self.IGNORED_PREFIXES):
            return False

        if any(part in request.path for part in self.TECHNICAL_PATH_PARTS):
            return False

        method = request.method.upper()
        if method not in self.MUTATING_METHODS and not self._is_action_get_request(
            request
        ):
            return False

        if self._is_handled_elsewhere(request):
            return False

        return True

    def _is_action_get_request(self, request):
        if request.method.upper() != "GET":
            return False

        path = request.path
        if request.GET.get("export") == "1":
            return True

        if "/export-detail-excel/" in path:
            return True

        export_paths = (
            "/veterinary/api/export-cares/",
            "/animals/api/export-excel/",
            "/animals/api/otbivka/export-excel/",
            "/animals/api/vet-list/export-excel/",
            "/animals/api/lambings/export-excel/",
            "/animals/api/archive/export-excel/",
            "/animals/api/kinship-pairs/export-excel/",
        )
        return any(export_path in path for export_path in export_paths)

    def _is_handled_elsewhere(self, request):
        method = request.method.upper()
        path = request.path

        # Animal card updates are logged in serializers with field-level details.
        if (
            method == "PATCH"
            and "/animals/" in path
            and any(animal_type in path for animal_type in ["/maker/", "/ram/", "/ewe/", "/sheep/"])
        ):
            return True

        # Veterinary CRUD (except DELETE) is logged in serializers.
        if (
            method in {"POST", "PUT", "PATCH"}
            and "/veterinary/api/" in path
            and any(
                vet_part in path
                for vet_part in ["/status/", "/place/", "/care/", "/veterinary/", "/weight-record/"]
            )
        ):
            return True

        # Calendar notes create/update are logged in serializers.
        if method in {"POST", "PUT", "PATCH"} and "/animals/notes/" in path:
            return True

        # Animal create endpoints are logged in serializers.
        if (
            method == "POST"
            and path.rstrip("/")
            in {
                "/animals/maker",
                "/animals/ram",
                "/animals/ewe",
                "/animals/sheep",
            }
        ):
            return True

        # Animal restore endpoints are logged in viewsets.
        if method == "POST" and "/animals/" in path and "/restore/" in path:
            return True

        # Animal delete endpoints are logged in viewsets.
        if (
            method == "DELETE"
            and "/animals/" in path
            and any(animal_type in path for animal_type in ["/maker/", "/ram/", "/ewe/", "/sheep/"])
        ):
            return True

        # Lambing mass/create-complete actions are already logged explicitly.
        if (
            method == "POST"
            and "/animals/" in path
            and any(
                lambing_path in path
                for lambing_path in ["/bulk-create-lambings/", "/complete/", "/complete-with-children/"]
            )
        ):
            return True

        return False

    @staticmethod
    def _truncate(value, max_length):
        if value is None:
            return value
        value_str = str(value)
        if not max_length:
            return value_str
        return value_str[:max_length]

    def determine_action(self, request):
        path = request.path
        method = request.method.upper()

        # Backups
        if "/backup/" in path:
            if method == "POST" and "/create/" in path:
                return "Создание резервной копии"
            if method == "POST" and "/restore/" in path:
                return "Восстановление из резервной копии"
            if method == "DELETE":
                return "Удаление резервной копии"

        # Calendar notes
        if "/animals/notes/" in path:
            if method == "POST":
                return "Создание заметки календаря"
            if method in {"PUT", "PATCH"}:
                return "Редактирование заметки календаря"
            if method == "DELETE":
                return "Удаление заметки календаря"

        # Shift transfer journal page actions (POST form)
        if "/animals/journals/shift-transfer/" in path and method == "POST":
            post_action = request.POST.get("action")
            if post_action == "create":
                return "Создание заметки передачи смены"
            if post_action == "update":
                return "Редактирование заметки передачи смены"
            return "Изменение заметки передачи смены"

        # Animals module actions
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
            if method == "GET" and request.GET.get("export") == "1":
                if "/journals/progeny/" in path:
                    return "Экспорт журнала Приплод"
                if "/journals/insemination/" in path:
                    return "Экспорт журнала Осеменение"
                if "/journals/three/" in path:
                    return "Экспорт Журнала 3"
                if "/journals/shift-transfer/" in path:
                    return "Экспорт журнала Передача смены"
                return "Экспорт данных"
            if method == "GET" and "/export-detail-excel/" in path:
                return "Экспорт карточки животного в Excel"

        # Veterinary module
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

        return f"{method} запрос к {path}"

    def get_object_type(self, request):
        path = request.path

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

    def get_object_id(self, request):
        path = request.path
        path_parts = path.strip("/").split("/")

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

    def get_request_details(self, request, response, action):
        details = {
            "action": action,
            "method": request.method,
            "path": request.path,
            "status_code": response.status_code,
        }

        if request.GET and len(request.GET) <= 10:
            details["params"] = dict(request.GET)

        if request.POST:
            # Store only field names, not values.
            details["changed_fields"] = list(request.POST.keys())

        if "/animals/journals/shift-transfer/" in request.path and request.method.upper() == "POST":
            post_action = request.POST.get("action")
            if post_action:
                details["journal_action"] = post_action

        return json.dumps(details, ensure_ascii=False, default=str)


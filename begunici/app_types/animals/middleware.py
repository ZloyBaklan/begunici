import json

from django.contrib.auth.models import AnonymousUser
from django.utils.deprecation import MiddlewareMixin

from .log_utils import (
    resolve_log_action,
    resolve_log_object_id,
    resolve_log_object_type,
)
from .models_user_log import UserActionLog


class UserActionLogMiddleware(MiddlewareMixin):
    """Middleware for user activity logging."""

    MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
    IGNORED_PREFIXES = ("/static/", "/admin/", "/login/")
    TECHNICAL_PATH_PARTS = (
        "/backup/check-auto/",
        "/api/archive/act-preview/",
        "/api/check-kinship/",
        "/api/health/",
        "/favicon.ico",
        "/robots.txt",
    )

    def process_response(self, request, response):
        if not self._should_log_request(request):
            return response

        if response.status_code < 400 and self._is_successfully_logged_elsewhere(request):
            return response

        action = self.determine_action(request, response=response)
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
            "/animals/api/lambing-groups/export-excel/",
            "/animals/api/archive/export-excel/",
            "/animals/api/archive/act/",
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

    def _is_successfully_logged_elsewhere(self, request):
        method = request.method.upper()
        path = request.path

        if method == "POST" and "/animals/lambing-group/" in path:
            if path.rstrip("/") == "/animals/lambing-group":
                return True
            if "/remove-father/" in path:
                return True

        if method == "POST" and "/animals/lambing/" in path:
            return any(
                lambing_path in path
                for lambing_path in [
                    "/complete/",
                    "/complete-with-children/",
                    "/complete-early-failure/",
                ]
            )

        return False

    @staticmethod
    def _truncate(value, max_length):
        if value is None:
            return value
        value_str = str(value)
        if not max_length:
            return value_str
        return value_str[:max_length]

    def determine_action(self, request, response=None):
        params = dict(request.GET)
        if (
            "/animals/journals/shift-transfer/" in request.path
            and request.method.upper() == "POST"
        ):
            params["action"] = request.POST.get("action")

        return resolve_log_action(
            request.method,
            request.path,
            params=params,
            status_code=getattr(response, "status_code", None),
        )

    def get_object_type(self, request):
        return resolve_log_object_type(request.method, request.path)

    def get_object_id(self, request):
        return resolve_log_object_id(request.method, request.path)

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


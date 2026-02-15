import json
import pytz
from django.utils import timezone
from django.utils.deprecation import MiddlewareMixin
from django.contrib.auth.models import AnonymousUser
from .models_user_log import UserActionLog


class UserActionLogMiddleware(MiddlewareMixin):
    """Middleware для логирования действий пользователей"""
    
    def __init__(self, get_response):
        self.get_response = get_response
        super().__init__(get_response)

    def process_response(self, request, response):
        # Логируем только для аутентифицированных пользователей
        if isinstance(request.user, AnonymousUser):
            return response
            
        # Логируем только POST, PUT, PATCH, DELETE запросы
        if request.method not in ['POST', 'PUT', 'PATCH', 'DELETE']:
            return response
            
        # Пропускаем статические файлы и админку Django
        if (request.path.startswith('/static/') or 
            request.path.startswith('/admin/') or
            request.path.startswith('/site/login/')):
            return response
        
        # Пропускаем автоматические и технические запросы
        technical_paths = [
            '/backup/check-auto/',
            '/api/health/',
            '/favicon.ico',
            '/robots.txt'
        ]
        if any(tech_path in request.path for tech_path in technical_paths):
            return response
        
        # Пропускаем GET запросы к API (они обычно не изменяют данные)
        if request.method == 'GET' and '/api/' in request.path:
            return response
        
        # Пропускаем PATCH запросы к животным - они логируются в сериализаторе с подробностями
        if (request.method == 'PATCH' and '/animals/' in request.path and 
            any(animal_type in request.path for animal_type in ['/maker/', '/ram/', '/ewe/', '/sheep/'])):
            return response
        
        # Пропускаем POST/PUT/PATCH запросы к ветеринарным данным - они логируются в сериализаторах с подробностями
        if (request.method in ['POST', 'PUT', 'PATCH'] and '/veterinary/api/' in request.path and 
            any(vet_type in request.path for vet_type in ['/status/', '/place/', '/care/', '/veterinary/', '/weight-record/'])):
            return response
        
        # Пропускаем POST/PUT/PATCH запросы к заметкам календаря - они логируются в сериализаторе с подробностями
        if (request.method in ['POST', 'PUT', 'PATCH'] and '/animals/notes/' in request.path):
            return response
        
        # Пропускаем POST запросы к созданию животных - они логируются в сериализаторах с подробностями
        if (request.method == 'POST' and '/animals/' in request.path and 
            any(animal_type in request.path for animal_type in ['/maker/', '/ram/', '/ewe/', '/sheep/'])):
            return response
        
        # Пропускаем DELETE запросы к животным - они логируются в ViewSet с подробностями
        if (request.method == 'DELETE' and '/animals/' in request.path and 
            any(animal_type in request.path for animal_type in ['/maker/', '/ram/', '/ewe/', '/sheep/'])):
            return response
        
        # Пропускаем POST запросы к окотам - они логируются в ViewSet с подробностями
        if (request.method == 'POST' and '/animals/' in request.path and 
            any(lambing_path in request.path for lambing_path in ['/bulk-create-lambings/', '/complete/', '/complete-with-children/', '/lambing/'])):
            return response

        # Определяем действие на основе URL и метода
        action = self.determine_action(request)
        
        if action:
            # Получаем детали запроса
            details = self.get_request_details(request)
            
            # Создаем запись в логе с московским временем
            moscow_tz = pytz.timezone('Europe/Moscow')
            current_time = timezone.now().astimezone(moscow_tz)
            
            UserActionLog.objects.create(
                user=request.user,
                action_type=action,
                object_type=self.get_object_type(request),
                object_id=self.get_object_id(request),
                description=details
                # Убираем ip_address
            )

        return response

    def determine_action(self, request):
        """Определяет тип действия на основе URL и метода"""
        path = request.path
        method = request.method
        
        # Заметки календаря
        if '/animals/notes/' in path:
            if method == 'POST':
                return 'Создание заметки календаря'
            elif method in ['PUT', 'PATCH']:
                return 'Редактирование заметки календаря'
            elif method == 'DELETE':
                return 'Удаление заметки календаря'
        
        # Животные
        elif '/animals/' in path:
            if method == 'POST':
                if '/create/' in path:
                    return 'Создание животного'
                elif '/lambing/' in path:
                    return 'Создание окота'
                elif '/complete_lambing/' in path:
                    return 'Завершение окота'
                elif '/vet_record/' in path:
                    return 'Добавление ветеринарной обработки'
                elif '/weight/' in path:
                    return 'Добавление записи о весе'
                elif '/calendar_note/' in path:
                    return 'Создание заметки календаря'
            elif method in ['PUT', 'PATCH']:
                if '/archive/' in path:
                    return 'Перенос в архив'
                elif '/restore/' in path:
                    return 'Восстановление из архива'
                elif '/update/' in path:
                    return 'Редактирование животного'
                elif '/move/' in path:
                    return 'Перемещение животного'
                else:
                    # Для обычных PATCH запросов к животным
                    return 'Редактирование животного'
            elif method == 'DELETE':
                return 'Удаление животного'
        
        # Ветеринария
        elif '/veterinary/' in path:
            if method == 'POST':
                if '/api/care/' in path:
                    return 'Создание ветеринарной обработки'
                elif '/api/place/' in path:
                    return 'Создание овчарни'
                elif '/api/status/' in path:
                    return 'Создание статуса'
            elif method in ['PUT', 'PATCH']:
                if '/api/care/' in path:
                    return 'Редактирование ветеринарной обработки'
                elif '/api/place/' in path:
                    return 'Редактирование овчарни'
                elif '/api/status/' in path:
                    return 'Редактирование статуса'
            elif method == 'DELETE':
                if '/api/care/' in path:
                    return 'Удаление ветеринарной обработки'
                elif '/api/place/' in path:
                    return 'Удаление овчарни'
                elif '/api/status/' in path:
                    return 'Удаление статуса'
        
        return f'{method} запрос к {path}'

    def get_object_type(self, request):
        """Определяет тип объекта"""
        path = request.path
        if '/animals/notes/' in path:
            return 'Заметка календаря'
        elif '/maker/' in path:
            return 'Производитель'
        elif '/ram/' in path:
            return 'Баран'
        elif '/ewe/' in path:
            return 'Ярка'
        elif '/sheep/' in path:
            return 'Овца'
        elif '/veterinary/api/care/' in path or '/cares/' in path:
            return 'Ветеринарная обработка'
        elif '/veterinary/api/place/' in path or '/places/' in path:
            return 'Овчарня'
        elif '/veterinary/api/status/' in path or '/statuses/' in path:
            return 'Статус'
        elif '/lambing/' in path:
            return 'Окот'
        return 'Неизвестно'

    def get_object_id(self, request):
        """Извлекает бирку животного или ID объекта из URL"""
        path_parts = request.path.strip('/').split('/')
        
        # Для животных пытаемся найти бирку
        if '/animals/' in request.path and not '/notes/' in request.path:
            for i, part in enumerate(path_parts):
                if part in ['maker', 'ram', 'ewe', 'sheep'] and i + 1 < len(path_parts):
                    return path_parts[i + 1]  # Возвращаем бирку
        
        # Для заметок календаря возвращаем дату
        if '/animals/notes/' in request.path:
            # Для заметок используем дату как идентификатор
            return ''  # Дата будет добавлена в сериализаторе
        
        # Для ветеринарных данных возвращаем пустую строку, так как ID не важен
        if '/veterinary/' in request.path:
            return ''
                
        # Для других случаев ищем ID
        for i, part in enumerate(path_parts):
            if part.isdigit():
                return part
                
        return ''

    def get_request_details(self, request):
        """Получает детали запроса"""
        details = {}
        
        # Для ветеринарных данных делаем более понятные детали
        if '/veterinary/' in request.path:
            if '/api/status/' in request.path:
                if request.method in ['PUT', 'PATCH']:
                    details['action'] = 'Изменение параметров статуса'
                elif request.method == 'POST':
                    details['action'] = 'Создание нового статуса'
                elif request.method == 'DELETE':
                    details['action'] = 'Удаление статуса'
            elif '/api/place/' in request.path:
                if request.method in ['PUT', 'PATCH']:
                    details['action'] = 'Изменение параметров овчарни'
                elif request.method == 'POST':
                    details['action'] = 'Создание новой овчарни'
                elif request.method == 'DELETE':
                    details['action'] = 'Удаление овчарни'
            elif '/api/care/' in request.path:
                if request.method in ['PUT', 'PATCH']:
                    details['action'] = 'Изменение параметров ветеринарной обработки'
                elif request.method == 'POST':
                    details['action'] = 'Создание новой ветеринарной обработки'
                elif request.method == 'DELETE':
                    details['action'] = 'Удаление ветеринарной обработки'
        else:
            # Для других запросов
            details['method'] = request.method
            details['path'] = request.path
            
            # Для POST запросов записываем только ключи полей, а не значения (для безопасности)
            if request.POST:
                details['changed_fields'] = list(request.POST.keys())
            
            # Для PATCH/PUT запросов пытаемся получить информацию о том, что изменилось
            if request.method in ['PATCH', 'PUT']:
                if hasattr(request, 'content_type') and 'json' in request.content_type:
                    details['action'] = 'Обновление данных'
                else:
                    details['action'] = 'Изменение данных'
            
            # Записываем GET параметры только если они есть и не слишком много
            if request.GET and len(request.GET) <= 5:
                details['params'] = dict(request.GET)
            
        return json.dumps(details, ensure_ascii=False, default=str)
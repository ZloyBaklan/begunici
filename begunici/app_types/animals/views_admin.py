from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.db.models import Q
from .models_user_log import UserActionLog
import pytz


@login_required
def admin_panel(request):
    """Панель администратора для просмотра логов действий"""
    # Проверяем, что пользователь в группе Admin
    if not request.user.groups.filter(name='Admin').exists():
        return render(request, 'error.html', {
            'error_message': 'У вас нет прав доступа к панели администратора'
        })
    
    return render(request, 'admin_panel.html')


@login_required
def admin_logs_api(request):
    """API для получения логов действий пользователей"""
    try:
        # Проверяем права доступа
        if not request.user.groups.filter(name='Admin').exists():
            return JsonResponse({'error': 'Нет прав доступа'}, status=403)
        
        # Получаем параметры пагинации и поиска
        page = int(request.GET.get('page', 1))
        search = request.GET.get('search', '')
        user_filter = request.GET.get('user', '')
        date_filter = request.GET.get('date', '')
        
        # Базовый queryset - сортируем по убыванию времени (самые новые сверху)
        logs = UserActionLog.objects.select_related('user').order_by('-timestamp')
        
        # Применяем фильтры
        if search:
            logs = logs.filter(
                Q(action_type__icontains=search) |
                Q(object_type__icontains=search) |
                Q(description__icontains=search)
            )
        
        if user_filter:
            logs = logs.filter(user__username__icontains=user_filter)
        
        if date_filter:
            from datetime import datetime
            try:
                # Парсим дату в формате YYYY-MM-DD
                filter_date = datetime.strptime(date_filter, '%Y-%m-%d').date()
                # Фильтруем по дате (без учета времени)
                logs = logs.filter(timestamp__date=filter_date)
            except ValueError:
                # Если дата некорректная, игнорируем фильтр
                pass
        
        # Пагинация
        paginator = Paginator(logs, 50)  # 50 записей на страницу
        page_obj = paginator.get_page(page)
        
        # Преобразуем в JSON с учетом московского времени
        moscow_tz = pytz.timezone('Europe/Moscow')
        logs_data = []
        
        for log in page_obj:
            # Преобразуем время в московское
            moscow_time = log.timestamp.astimezone(moscow_tz)
            
            # Проверяем, является ли object_id биркой животного или парой биркий
            animal_link_info = None
            if log.object_id:
                # Импортируем модели животных
                from begunici.app_types.animals.models import Maker, Ram, Ewe, Sheep
                
                # Проверяем, если это пара биркий (формат "бирка1, бирка2")
                if ', ' in log.object_id:
                    # Разделяем бирки
                    tags = [tag.strip() for tag in log.object_id.split(', ')]
                    if len(tags) == 2:
                        # Создаем информацию для обеих биркий
                        animal_link_info = {'pair_tags': []}
                        
                        animal_types = [
                            (Maker, 'maker', 'Производитель'),
                            (Ram, 'ram', 'Баран'),
                            (Ewe, 'ewe', 'Ярка'),
                            (Sheep, 'sheep', 'Овца')
                        ]
                        
                        for tag in tags:
                            tag_info = None
                            for model_class, url_type, russian_name in animal_types:
                                try:
                                    if model_class.objects.filter(tag__tag_number=tag).exists():
                                        tag_info = {
                                            'tag': tag,
                                            'url_type': url_type,
                                            'russian_name': russian_name
                                        }
                                        break
                                except:
                                    continue
                            
                            if tag_info:
                                animal_link_info['pair_tags'].append(tag_info)
                            else:
                                animal_link_info['pair_tags'].append({'tag': tag, 'url_type': None})
                else:
                    # Проверяем каждый тип животного для одиночной бирки
                    animal_types = [
                        (Maker, 'maker', 'Производитель'),
                        (Ram, 'ram', 'Баран'),
                        (Ewe, 'ewe', 'Ярка'),
                        (Sheep, 'sheep', 'Овца')
                    ]
                    
                    for model_class, url_type, russian_name in animal_types:
                        try:
                            if model_class.objects.filter(tag__tag_number=log.object_id).exists():
                                animal_link_info = {
                                    'url_type': url_type,
                                    'russian_name': russian_name
                                }
                                break
                        except:
                            continue
            
            # Парсим детали для более понятного отображения
            details_text = log.description or ''
            if details_text:
                try:
                    import json
                    details_json = json.loads(details_text)
                    
                    # Если есть поле action, используем его как основное описание
                    if 'action' in details_json:
                        details_text = details_json['action']
                        # Добавляем тип если есть
                        if 'type' in details_json:
                            details_text += f" ({details_json['type']})"
                    else:
                        # Для других случаев формируем описание из доступных полей
                        if 'method' in details_json and 'path' in details_json:
                            details_text = f"{details_json['method']} запрос к {details_json['path']}"
                        elif 'changed_fields' in details_json:
                            details_text = f"Изменены поля: {', '.join(details_json['changed_fields'])}"
                except (json.JSONDecodeError, TypeError):
                    # Если не удалось распарсить JSON, оставляем как есть
                    pass
            
            logs_data.append({
                'id': log.id,
                'user': log.user.username,
                'action': log.action_type,
                'object_type': log.object_type or '',
                'object_id': log.object_id or '',
                'details': details_text,
                'timestamp': moscow_time.strftime('%d.%m.%Y %H:%M:%S'),
                'animal_link_info': animal_link_info
            })
        
        return JsonResponse({
            'logs': logs_data,
            'has_next': page_obj.has_next(),
            'has_previous': page_obj.has_previous(),
            'current_page': page,
            'total_pages': paginator.num_pages,
            'total_count': paginator.count
        })
    except Exception as e:
        return JsonResponse({'error': f'Ошибка сервера: {str(e)}'}, status=500)
from django.contrib import admin
from .models import Maker, Ram, Ewe, Sheep, Lambing

admin.site.register(Maker)
admin.site.register(Ram)
admin.site.register(Lambing)

# Функция действия для преобразования ярки в овцу
def convert_to_sheep(modeladmin, request, queryset):
    for ewe in queryset:
        ewe.to_sheep()
    modeladmin.message_user(request, "Выбранные ярки успешно переведены в овец")

# Админ-класс для Ewe с кастомным действием
class EweAdmin(admin.ModelAdmin):
    list_display = ('tag', 'animal_status', 'birth_date', 'place')
    actions = [convert_to_sheep]  # Добавляем действие в админку


class SheepAdmin(admin.ModelAdmin):
    def get_fields(self, request, obj=None):
        fields = super().get_fields(request, obj)
        if obj and 'lambing_history' not in fields:  # Проверяем, есть ли уже поле в списке
            fields.append('lambing_history')  # Добавляем только при редактировании
        return fields


# Регистрируем модель с кастомным админом
admin.site.register(Sheep, SheepAdmin)
admin.site.register(Ewe, EweAdmin)

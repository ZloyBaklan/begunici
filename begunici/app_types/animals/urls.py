from django.urls import path, include
from django.views.generic import TemplateView
from rest_framework.routers import DefaultRouter
from .views import (
    MakerViewSet,
    MakersView,
    MakerDetailView,
    MakerAnalyticsView,
    RamAnalyticsView,
    EweAnalyticsView,
    SheepAnalyticsView,
    RamViewSet,
    EweViewSet,
    SheepViewSet,
    LambingViewSet,
    LambingGroupViewSet,
    CalendarNoteViewSet,
    animals,
    create_animal,
    common_animals,
    common_animals_api,
    young_stock,
    young_stock_api,
    young_stock_export_excel,
    ArchiveViewSet,
    ArchiveView,
    AnimalActionsViewSet,
    RamDetailView,
    EweDetailView,
    SheepDetailView,
    dashboard_statistics,
    yearly_statistics,
    get_all_tags,
    get_all_statuses,
    export_to_excel,
    export_animal_detail_excel,
    create_backup,
    backup_info,
    check_auto_backup,
    get_inactive_mothers,
    get_all_fathers,
    bulk_create_lambings,
    otbivka_list,
    otbivka_api,
    otbivka_export_excel,
    vet_list,
    vet_list_api,
    vet_list_export_excel,
    vet_filter_options,
    lambings_export_excel,
    lambing_groups_export_excel,
    archive_export_excel,
    archive_acts_api,
    archive_act_preview,
    archive_act_download,
    transfer_acts_api,
    transfer_act_download,
    manual_transfer_act_download,
    weight_acts_api,
    weight_act_download,
    progeny_acts_api,
    progeny_act_download,
    monthly_breeding_act_download,
    livestock_movement_act_download,
    non_auto_act_templates_api,
    non_auto_act_template_download,
    check_kinship,
    kinship_pairs_export_excel,
    get_animals_without_otbivka,
    bulk_otbivka,
    bulk_place_move,
    bulk_vaccination,
    journals_menu,
    journal_progeny,
    journal_insemination,
    journal_three,
    journal_shift_transfer,
)
from .excel_imports import (
    import_confirm,
    import_preview,
    import_template_download,
)

# Создаем маршруты для ViewSet
router = DefaultRouter()
router.register(r"maker", MakerViewSet)  # Маршрут для производителей
router.register(r"ram", RamViewSet)  # Маршрут для баранов
router.register(r"ewe", EweViewSet)  # Маршрут для ярок
router.register(r"sheep", SheepViewSet)  # Маршрут для овец
router.register(r"lambing", LambingViewSet)  # Маршрут для окотов
router.register(r"lambing-group", LambingGroupViewSet)  # Маршрут для групп случек
router.register(r"notes", CalendarNoteViewSet)  # Маршрут для заметок календаря
router.register(r"archive", ArchiveViewSet, basename="archive")  # Архив животных
router.register(r"actions", AnimalActionsViewSet, basename="actions")  # Действия с животными

# Подключаем router для управления всеми ViewSet
urlpatterns = [
    path(
        "maker/<str:tag_number>/info/", MakerDetailView.as_view(), name="maker-detail"
    ),
    path(
        "maker/<str:tag_number>/analytics/",
        MakerAnalyticsView.as_view(),
        name="maker-analytics",
    ),
    path(
        "ram/<str:tag_number>/analytics/",
        RamAnalyticsView.as_view(),
        name="ram-analytics",
    ),
    path(
        "ewe/<str:tag_number>/analytics/",
        EweAnalyticsView.as_view(),
        name="ewe-analytics",
    ),
    path(
        "sheep/<str:tag_number>/analytics/",
        SheepAnalyticsView.as_view(),
        name="sheep-analytics",
    ),
    path(
        "ram/<str:tag_number>/info/", RamDetailView.as_view(), name="ram-detail"
    ),
    path(
        "ewe/<str:tag_number>/info/", EweDetailView.as_view(), name="ewe-detail"
    ),
    path(
        "sheep/<str:tag_number>/info/", SheepDetailView.as_view(), name="sheep-detail"
    ),
    path(
        "main_archive/",
        ArchiveView.as_view(),
        name="main_archive",
    ),
    path("", include(router.urls)),
    path(
        "maker/<str:tag_number>/api/",
        MakerViewSet.as_view({"get": "retrieve_api"}),
        name="maker-api",
    ),
    path(
        "ram/<str:tag_number>/api/",
        RamViewSet.as_view({"get": "retrieve_api"}),
        name="ram-api",
    ),
    path(
        "ewe/<str:tag_number>/api/",
        EweViewSet.as_view({"get": "retrieve_api"}),
        name="ewe-api",
    ),
    path(
        "sheep/<str:tag_number>/api/",
        SheepViewSet.as_view({"get": "retrieve_api"}),
        name="sheep-api",
    ),
    path(
        "maker/<str:tag_number>/update_parents/",
        MakerViewSet.as_view({"patch": "update_parents"}),
        name="update-parents",
    ),
    path(
        "ram/<str:tag_number>/update_parents/",
        RamViewSet.as_view({"patch": "update_parents"}),
        name="update-ram-parents",
    ),
    path(
        "ewe/<str:tag_number>/update_parents/",
        EweViewSet.as_view({"patch": "update_parents"}),
        name="update-ewe-parents",
    ),
    path(
        "sheep/<str:tag_number>/update_parents/",
        SheepViewSet.as_view({"patch": "update_parents"}),
        name="update-sheep-parents",
    ),
    # path('maker/<int:pk>/weight_history/', MakerViewSet.as_view({'get': 'weight_history'}), name='weight-history'),
    # path('maker/<int:pk>/add_weight/', MakerViewSet.as_view({'post': 'add_weight'}), name='add-weight'),
    # path('maker/<int:pk>/vet_history/', MakerViewSet.as_view({'get': 'vet_history'}), name='vet-history'),
    # path('maker/<int:pk>/place_history/', MakerViewSet.as_view({'get': 'place_history'}), name='place-history'),
    # path('maker/place_movement/', MakerViewSet.as_view({'post': 'add_place_movement'}), name='add-place-movement'),
    path(
        "maker/<str:tag_number>/children/",
        MakerViewSet.as_view({"get": "children"}),
        name="maker-children",
    ),
    path(
        "ram/<str:tag_number>/children/",
        RamViewSet.as_view({"get": "children"}),
        name="ram-children",
    ),
    path(
        "ewe/<str:tag_number>/children/",
        EweViewSet.as_view({"get": "children"}),
        name="ewe-children",
    ),
    path(
        "sheep/<str:tag_number>/children/",
        SheepViewSet.as_view({"get": "children"}),
        name="sheep-children",
    ),
    path(
        "maker/<str:tag_number>/status_history/",
        MakerViewSet.as_view({"get": "status_history"}),
        name="maker-status-history",
    ),
    path(
        "ram/<str:tag_number>/status_history/",
        RamViewSet.as_view({"get": "status_history"}),
        name="ram-status-history",
    ),
    path(
        "ewe/<str:tag_number>/status_history/",
        EweViewSet.as_view({"get": "status_history"}),
        name="ewe-status-history",
    ),
    path(
        "sheep/<str:tag_number>/status_history/",
        SheepViewSet.as_view({"get": "status_history"}),
        name="sheep-status-history",
    ),
    path(
        "maker/<str:tag_number>/place_history/",
        MakerViewSet.as_view({"get": "place_history"}),
        name="maker-place-history",
    ),
    path(
        "ram/<str:tag_number>/place_history/",
        RamViewSet.as_view({"get": "place_history"}),
        name="ram-place-history",
    ),
    path(
        "ewe/<str:tag_number>/place_history/",
        EweViewSet.as_view({"get": "place_history"}),
        name="ewe-place-history",
    ),
    path(
        "sheep/<str:tag_number>/place_history/",
        SheepViewSet.as_view({"get": "place_history"}),
        name="sheep-place-history",
    ),
    path(
        "maker/<str:tag_number>/note_history/",
        MakerViewSet.as_view({"get": "note_history"}),
        name="maker-note-history",
    ),
    path(
        "ram/<str:tag_number>/note_history/",
        RamViewSet.as_view({"get": "note_history"}),
        name="ram-note-history",
    ),
    path(
        "ewe/<str:tag_number>/note_history/",
        EweViewSet.as_view({"get": "note_history"}),
        name="ewe-note-history",
    ),
    path(
        "sheep/<str:tag_number>/note_history/",
        SheepViewSet.as_view({"get": "note_history"}),
        name="sheep-note-history",
    ),
    path(
        "maker/<str:tag_number>/restore/",
        MakerViewSet.as_view({"post": "restore"}),
        name="maker-restore",
    ),
    path(
        "ram/<str:tag_number>/restore/",
        RamViewSet.as_view({"post": "restore"}),
        name="ram-restore",
    ),
    path(
        "ewe/<str:tag_number>/restore/",
        EweViewSet.as_view({"post": "restore"}),
        name="ewe-restore",
    ),
    path(
        "sheep/<str:tag_number>/restore/",
        SheepViewSet.as_view({"post": "restore"}),
        name="sheep-restore",
    ),
    path("api/dashboard-statistics/", dashboard_statistics, name="dashboard-statistics"),  # API статистики
    path("api/yearly-statistics/", yearly_statistics, name="yearly-statistics"),  # API годовой статистики
    path("api/all-tags/", get_all_tags, name="all-tags"),  # API всех бирок
    path("api/all-statuses/", get_all_statuses, name="all-statuses"),  # API всех статусов
    path("api/common/", common_animals_api, name="common-animals-api"),  # API общего списка животных
    path("api/export-excel/", export_to_excel, name="export-excel"),  # API экспорта в Excel
    path(
        "api/<str:animal_type>/<str:tag_number>/export-detail-excel/",
        export_animal_detail_excel,
        name="export-animal-detail-excel",
    ),
    path("main/", animals, name="animals"),  # Главная страница
    path("common/", common_animals, name="common"),  # Общая страница животных
    path("young-stock/", young_stock, name="young-stock"),
    path("otbivka/", otbivka_list, name="otbivka"),  # Страница списка отбивки
    path("vet-list/", vet_list, name="vet-list"),  # Страница списка ветобработок
    path("acts/", TemplateView.as_view(template_name="acts_menu.html"), name="acts"),
    path("acts/archive/", TemplateView.as_view(template_name="archive_acts_list.html"), name="acts-archive"),
    path("acts/transfer/", TemplateView.as_view(template_name="transfer_acts_list.html"), name="acts-transfer"),
    path("acts/weight/", TemplateView.as_view(template_name="weight_acts_list.html"), name="acts-weight"),
    path("acts/progeny/", TemplateView.as_view(template_name="progeny_acts_list.html"), name="acts-progeny"),
    path("journals/", journals_menu, name="journals"),  # Меню журналов
    path("journals/progeny/", journal_progeny, name="journal-progeny"),  # Журнал приплода
    path("journals/insemination/", journal_insemination, name="journal-insemination"),  # Журнал осеменения
    path("journals/three/", journal_three, name="journal-three"),  # Журнал 3
    path("journals/shift-transfer/", journal_shift_transfer, name="journal-shift-transfer"),  # Журнал передачи смены
    path("api/otbivka/", otbivka_api, name="otbivka-api"),  # API для списка отбивки
    path("api/otbivka/export-excel/", otbivka_export_excel, name="otbivka-export-excel"),  # API экспорта отбивки
    path("api/vet-list/", vet_list_api, name="vet-list-api"),  # API для списка ветобработок
    path("api/vet-list/export-excel/", vet_list_export_excel, name="vet-list-export-excel"),  # API экспорта ветобработок
    path("api/vet-filter-options/", vet_filter_options, name="vet-filter-options"),  # API для опций фильтров ветобработок
    path("api/lambings/export-excel/", lambings_export_excel, name="lambings-export-excel"),  # API экспорта окотов
    path("api/lambing-groups/export-excel/", lambing_groups_export_excel, name="lambing-groups-export-excel"),  # API экспорта групп
    path("api/archive/export-excel/", archive_export_excel, name="archive-export-excel"),  # API экспорта архива
    path("api/young-stock/", young_stock_api, name="young-stock-api"),
    path("api/young-stock/export-excel/", young_stock_export_excel, name="young-stock-export-excel"),
    path("api/archive/act-preview/", archive_act_preview, name="archive-act-preview"),
    path("api/acts/archive/", archive_acts_api, name="archive-acts-api"),
    path("api/archive/act/<str:animal_type>/<str:tag_number>/", archive_act_download, name="archive-act-download"),
    path("api/acts/transfer/", transfer_acts_api, name="transfer-acts-api"),
    path("api/acts/transfer/<int:act_number>/", transfer_act_download, name="transfer-act-download"),
    path("api/acts/transfer/manual/", manual_transfer_act_download, name="manual-transfer-act-download"),
    path("api/acts/weight/", weight_acts_api, name="weight-acts-api"),
    path("api/acts/weight/<int:act_number>/", weight_act_download, name="weight-act-download"),
    path("api/acts/progeny/", progeny_acts_api, name="progeny-acts-api"),
    path("api/acts/progeny/<int:act_number>/", progeny_act_download, name="progeny-act-download"),
    path("api/acts/monthly-breeding/", monthly_breeding_act_download, name="monthly-breeding-act-download"),
    path("api/acts/livestock-movement/", livestock_movement_act_download, name="livestock-movement-act-download"),
    path("api/acts/templates/", non_auto_act_templates_api, name="act-templates-api"),
    path("api/acts/templates/download/", non_auto_act_template_download, name="act-template-download"),
    path("calendar/notes/", TemplateView.as_view(template_name="calendar_notes.html"), name="calendar-notes"),  # Страница заметок календаря
    path(
        "create/", create_animal, name="create_animal"
    ),  # Маршрут для создания животных
    path(
        "makers/", MakersView.as_view(), name="makers"
    ),  # Маршрут для страницы управления производителями
    path(
        "rams/", TemplateView.as_view(template_name="rams.html"), name="rams"
    ),  # Маршрут для страницы управления баранами
    path(
        "ewes/", TemplateView.as_view(template_name="ewes.html"), name="ewes"
    ),  # Маршрут для страницы управления ярками
    path(
        "sheeps/", TemplateView.as_view(template_name="sheeps.html"), name="sheeps"
    ),  # Маршрут для страницы управления овцами
    path(
        "lambings/", TemplateView.as_view(template_name="lambings_management.html"), name="lambings"
    ),  # Маршрут для страницы управления окотами
    
    # API для бэкапов
    path("api/backup/create/", create_backup, name="create-backup"),  # Создание ручного бэкапа
    path("api/backup/info/", backup_info, name="backup-info"),  # Информация о последнем бэкапе
    path("api/backup/check-auto/", check_auto_backup, name="check-auto-backup"),  # Проверка автобэкапа
    
    # API для управления окотами
    path("api/inactive-mothers/", get_inactive_mothers, name="inactive-mothers"),  # Неактивные матери
    path("api/all-fathers/", get_all_fathers, name="all-fathers"),  # Все отцы
    path("api/bulk-create-lambings/", bulk_create_lambings, name="bulk-create-lambings"),  # Массовое создание окотов
    path("api/check-kinship/", check_kinship, name="check-kinship"),  # Проверка родства
    path("api/kinship-pairs/export-excel/", kinship_pairs_export_excel, name="kinship-pairs-export-excel"),  # Экспорт подбора пар по родству
    
    # API для ковровой отбивки
    path("api/animals-without-otbivka/", get_animals_without_otbivka, name="animals-without-otbivka"),  # Животные без отбивки
    path("api/bulk-otbivka/", bulk_otbivka, name="bulk-otbivka"),  # Массовая отбивка
    path("api/bulk-place-move/", bulk_place_move, name="bulk-place-move"),  # Массовое перемещение животных
    
    # API для ковровой вакцинации
    path("api/bulk-vaccination/", bulk_vaccination, name="bulk-vaccination"),  # Массовая вакцинация

    # API для импортов из Excel
    path("api/import/<str:import_type>/template/", import_template_download, name="import-template-download"),
    path("api/import/<str:import_type>/preview/", import_preview, name="import-preview"),
    path("api/import/<str:import_type>/confirm/", import_confirm, name="import-confirm"),
]

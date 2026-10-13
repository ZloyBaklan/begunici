"""Initial rates from the existing korm_plan.xlsx, in base units per head/day.

Blank cells stay unassigned; a deliberate zero can be entered separately.
Migration imports these immutable defaults, never data from a changing workbook.
"""
GROUPS = [
    "makers", "pregnant_females", "lactating_females", "young_3_to_6_months",
    "young_7_to_12_months", "young_under_3_months", "rams_over_12_months", "non_inseminated_sheep",
]
PRODUCTS = [
    ("Сенаж", "hay", "рулон", [None] * 8),
    ("Пастбищная трава", "other", "", [None] * 8),
    ("Сено", "hay", "стог / тюк", ["3", "2.2", "2.5", "1.3", "1.8", "0.6", "3", "2.2"]),
    ("Комбикорм", "feed", "мешок", ["0.8", "0.3", "0.6", "0.6", "0.5", "0.3", "0.8", "0.3"]),
    ("Овёс фуражный", "feed", "мешок", ["0.2", "0.3", "0.2", None, "0.2", None, "0.2", "0.3"]),
    ("Соль глыба", "salt", "глыба", ["0.01", "0.01", "0.01", "0.005", "0.005", None, "0.01", "0.01"]),
    ("Премикс овец и ягнят", "feed", "мешок", ["0.01", "0.01", "0.01", "0.008", "0.01", "0.003", "0.01", "0.01"]),
]

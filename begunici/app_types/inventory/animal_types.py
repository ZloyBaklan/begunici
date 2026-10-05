"""Shared inventory labels; the core animal models remain the source of type."""

ANIMAL_TYPE_CHOICES = [
    ("maker", "Баран-производитель"),
    ("ram", "Баранчик"),
    ("ewe", "Ярка"),
    ("sheep", "Овцематка"),
]
ANIMAL_TYPE_LABELS = dict(ANIMAL_TYPE_CHOICES)
ANIMAL_TYPE_SEX = {"maker": "male", "ram": "male", "ewe": "female", "sheep": "female"}


def type_label(value):
    return ANIMAL_TYPE_LABELS.get(str(value).lower(), "—")


def type_requirement(animal_type, legacy_sex=""):
    if animal_type:
        return type_label(animal_type)
    # Older orders allowed both types of the same sex. Do not silently narrow
    # their requirements when displaying them with the new vocabulary.
    if legacy_sex:
        return " / ".join(label for key, label in ANIMAL_TYPE_CHOICES if ANIMAL_TYPE_SEX[key] == legacy_sex)
    return "Любой тип"

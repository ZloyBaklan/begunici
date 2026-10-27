from collections import defaultdict, deque
from decimal import Decimal, ROUND_HALF_UP


DEFAULT_DORPER_PERCENTAGE = Decimal("50")
DORPER_PRECISION = Decimal("0.00001")
DORPER_FIELDS = ("dorper_percentage", "dorper_uses_default")


class DorperCalculator:
    """Resolve ancestry without relying on stored automatic percentages."""

    def __init__(self, find_parent):
        self.find_parent = find_parent
        self.results = {}
        self.parents = {}

    def resolve(self, animal):
        stack = [animal]
        path = {}
        default = (DEFAULT_DORPER_PERCENTAGE, True)
        while stack:
            current = stack[-1]
            key = current["tag_id"]
            if key in self.results:
                stack.pop()
                path.pop(key, None)
                continue
            if current["is_manual_dorper"]:
                value = current["dorper_percentage"]
                self.results[key] = (Decimal(value), False) if value is not None else default
                continue

            path[key] = len(stack) - 1
            if key not in self.parents:
                self.parents[key] = tuple(
                    self.find_parent(current.get(field)) for field in ("father", "mother")
                )
            parents = self.parents[key]
            unresolved = next(
                (parent for parent in parents
                 if parent is not None and parent["tag_id"] not in self.results), None,
            )
            if unresolved is not None:
                parent_key = unresolved["tag_id"]
                if parent_key in path:
                    # Invalid ancestry must not recurse forever or invent a known percentage.
                    for cyclic in stack[path[parent_key]:]:
                        self.results[cyclic["tag_id"]] = default
                else:
                    stack.append(unresolved)
                continue

            values = [self.results[parent["tag_id"]] if parent is not None else default
                      for parent in parents]
            percentage = ((values[0][0] + values[1][0]) / 2).quantize(
                DORPER_PRECISION, rounding=ROUND_HALF_UP,
            )
            self.results[key] = (percentage, any(value[1] for value in values))
        return self.results[animal["tag_id"]]


def animal_dorper_record(animal):
    return {
        "tag_id": animal.tag_id,
        "dorper_percentage": animal.dorper_percentage,
        "is_manual_dorper": animal.is_manual_dorper,
        "mother": animal.mother,
        "father": animal.father,
    }


def make_parent_lookup(records):
    exact = {record["tag__tag_number"]: record for record in records}
    folded = defaultdict(list)
    for number, record in exact.items():
        folded[number.casefold()].append(record)

    def find_parent(number):
        number = str(number or "").strip()
        if not number:
            return None
        if number in exact:
            return exact[number]
        matches = folded.get(number.casefold(), ())
        return matches[0] if len(matches) == 1 else None

    return find_parent


def recalculate_dorper_values(animal_models, *, using="default", dry_run=False,
                             parent_tag_number=None):
    """Also accepts historical migration models; only writes the two calculated fields."""
    records = {}
    for model in animal_models:
        rows = model.objects.using(using).values(
            "pk", "tag_id", "tag__tag_number", "tag__animal_type", "mother", "father",
            "is_manual_dorper", *DORPER_FIELDS,
        )
        for row in rows:
            row["model"] = model
            existing = records.get(row["tag_id"])
            if existing is None or row["tag__animal_type"] == model.__name__:
                records[row["tag_id"]] = row

    find_parent = make_parent_lookup(records.values())
    selected = set(records)
    if parent_tag_number is not None:
        root = find_parent(parent_tag_number)
        if root is None:
            return []
        children = defaultdict(set)
        for row in records.values():
            if row["is_manual_dorper"]:
                continue
            for field in ("mother", "father"):
                parent = find_parent(row[field])
                if parent is not None:
                    children[parent["tag_id"]].add(row["tag_id"])
        selected = {root["tag_id"]}
        queue = deque(selected)
        while queue:
            for key in children[queue.popleft()] - selected:
                selected.add(key)
                queue.append(key)
        selected.discard(root["tag_id"])

    calculator = DorperCalculator(find_parent)
    changes = []
    pending = defaultdict(list)
    for key in sorted(selected):
        row = records[key]
        if row["is_manual_dorper"]:
            continue
        percentage, uses_default = calculator.resolve(row)
        if (row["dorper_percentage"], row["dorper_uses_default"]) == (percentage, uses_default):
            continue
        changes.append({
            "model": row["model"].__name__, "tag_number": row["tag__tag_number"],
            "old": row["dorper_percentage"], "new": percentage,
            "uses_default": uses_default,
        })
        pending[row["model"]].append(row["model"](
            pk=row["pk"], dorper_percentage=percentage, dorper_uses_default=uses_default,
        ))

    if not dry_run:
        for model, animals in pending.items():
            model.objects.using(using).bulk_update(animals, DORPER_FIELDS, batch_size=500)
    return changes

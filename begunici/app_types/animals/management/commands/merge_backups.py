import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


COPY_HEADER_RE = re.compile(r"^COPY\s+([^\s]+)\s+\((.+)\)\s+FROM stdin;$")

TAG_TABLE = "public.veterinary_tag"
WEIGHT_TABLE = "public.veterinary_weightrecord"

ANIMAL_CONFIGS = [
    {
        "animal_table": "public.animals_maker",
        "link_table": "public.animals_maker_weight_records",
        "animal_fk_column": "maker_id",
    },
    {
        "animal_table": "public.animals_ram",
        "link_table": "public.animals_ram_weight_records",
        "animal_fk_column": "ram_id",
    },
    {
        "animal_table": "public.animals_ewe",
        "link_table": "public.animals_ewe_weight_records",
        "animal_fk_column": "ewe_id",
    },
    {
        "animal_table": "public.animals_sheep",
        "link_table": "public.animals_sheep_weight_records",
        "animal_fk_column": "sheep_id",
    },
]


@dataclass
class CopySection:
    table_name: str
    columns: List[str]
    data_start: int
    data_end: int


@dataclass
class LinkStore:
    table_name: str
    columns: List[str]
    rows: List[List[str]]
    id_idx: int
    animal_fk_idx: int
    weight_fk_idx: int
    max_id: int
    used_ids: Set[str]
    existing_links: Set[Tuple[str, str]]


class Command(BaseCommand):
    help = (
        "Merge two SQL backups in weight-only mode by TAGS: "
        "transfer only weight data from secondary backup to main backup."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--main",
            type=str,
            help="Main backup file (absolute path or file name from backups/)",
        )
        parser.add_argument(
            "--secondary",
            type=str,
            help="Secondary backup file (absolute path or file name from backups/)",
        )
        parser.add_argument(
            "--output",
            type=str,
            help=(
                "Output file path (absolute path or file name for backups/). "
                "If omitted, file will be created in backups/ automatically."
            ),
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Overwrite output file if it already exists.",
        )
        parser.add_argument(
            "--list",
            action="store_true",
            help="List available .sql backups from backups/ and exit.",
        )

    def handle(self, *args, **options):
        backups_dir = Path(settings.BASE_DIR) / "backups"
        backups_dir.mkdir(parents=True, exist_ok=True)

        if options["list"]:
            self._print_backups_list(backups_dir)
            return

        main_raw = options.get("main")
        secondary_raw = options.get("secondary")
        if not main_raw or not secondary_raw:
            raise CommandError(
                "Specify both --main and --secondary. "
                "Use --list to see available files."
            )

        main_path = self._resolve_input_path(main_raw, backups_dir, "main")
        secondary_path = self._resolve_input_path(secondary_raw, backups_dir, "secondary")

        if main_path.resolve() == secondary_path.resolve():
            raise CommandError("Main and secondary backups must be different files.")

        output_path = self._resolve_output_path(
            output_raw=options.get("output"),
            backups_dir=backups_dir,
            main_path=main_path,
            secondary_path=secondary_path,
        )

        if output_path.exists() and not options["force"]:
            raise CommandError(
                f"Output file already exists: {output_path}. "
                "Use --force to overwrite."
            )

        self.stdout.write(f"Main backup: {main_path}")
        self.stdout.write(f"Secondary backup: {secondary_path}")
        self.stdout.write(f"Output file: {output_path}")
        self.stdout.write("Mode: WEIGHT-ONLY (tag-based)")

        main_lines = self._read_sql_lines(main_path)
        secondary_lines = self._read_sql_lines(secondary_path)

        main_sections = self._parse_copy_sections(main_lines)
        secondary_sections = self._parse_copy_sections(secondary_lines)

        if not main_sections:
            raise CommandError(f"No COPY sections found in main backup: {main_path}")
        if not secondary_sections:
            raise CommandError(f"No COPY sections found in secondary backup: {secondary_path}")

        for required_table in (TAG_TABLE, WEIGHT_TABLE):
            if required_table not in main_sections:
                raise CommandError(f"Required table missing in main backup: {required_table}")
            if required_table not in secondary_sections:
                raise CommandError(f"Required table missing in secondary backup: {required_table}")

        stats = {
            "weights_added": 0,
            "links_added": 0,
            "secondary_weights_total": 0,
            "secondary_weights_mapped_to_main_tag": 0,
            "secondary_weights_skipped_no_tag_in_secondary": 0,
            "secondary_weights_skipped_tag_absent_in_main": 0,
            "secondary_weights_reused_existing_main": 0,
            "weights_without_animal_in_main": 0,
            "rows_skipped_format": 0,
            "link_tables_missing_in_main": 0,
        }

        merged_lines = list(main_lines)
        rows_replacements: Dict[str, List[List[str]]] = {}

        # --- TAG maps ---
        main_tag_section = main_sections[TAG_TABLE]
        sec_tag_section = secondary_sections[TAG_TABLE]
        main_tag_rows, skipped_main_tags = self._read_section_rows(main_lines, main_tag_section)
        sec_tag_rows, skipped_sec_tags = self._read_section_rows(secondary_lines, sec_tag_section)
        stats["rows_skipped_format"] += skipped_main_tags + skipped_sec_tags

        main_tag_id_idx = self._column_index(main_tag_section.columns, "id", TAG_TABLE)
        main_tag_number_idx = self._column_index(main_tag_section.columns, "tag_number", TAG_TABLE)
        sec_tag_id_idx = self._column_index(sec_tag_section.columns, "id", TAG_TABLE)
        sec_tag_number_idx = self._column_index(sec_tag_section.columns, "tag_number", TAG_TABLE)

        main_tag_number_to_id: Dict[str, str] = {}
        for row_values in main_tag_rows:
            main_tag_number_to_id[row_values[main_tag_number_idx]] = row_values[main_tag_id_idx]

        sec_tag_id_to_number: Dict[str, str] = {}
        for row_values in sec_tag_rows:
            sec_tag_id_to_number[row_values[sec_tag_id_idx]] = row_values[sec_tag_number_idx]

        # --- Main animals and link tables ---
        main_tag_id_to_animal_ref: Dict[str, Tuple[str, str]] = {}
        link_stores: Dict[str, LinkStore] = {}

        for cfg in ANIMAL_CONFIGS:
            animal_table = cfg["animal_table"]
            link_table = cfg["link_table"]
            animal_fk_column = cfg["animal_fk_column"]

            animal_section = main_sections.get(animal_table)
            link_section = main_sections.get(link_table)
            if not animal_section or not link_section:
                stats["link_tables_missing_in_main"] += 1
                continue

            animal_rows, skipped_animals = self._read_section_rows(main_lines, animal_section)
            stats["rows_skipped_format"] += skipped_animals

            animal_id_idx = self._column_index(animal_section.columns, "id", animal_table)
            animal_tag_idx = self._column_index(animal_section.columns, "tag_id", animal_table)

            for row_values in animal_rows:
                tag_id = row_values[animal_tag_idx]
                animal_id = row_values[animal_id_idx]
                if tag_id and animal_id and tag_id not in main_tag_id_to_animal_ref:
                    main_tag_id_to_animal_ref[tag_id] = (link_table, animal_id)

            link_rows, skipped_links = self._read_section_rows(main_lines, link_section)
            stats["rows_skipped_format"] += skipped_links

            link_id_idx = self._column_index(link_section.columns, "id", link_table)
            link_animal_idx = self._column_index(link_section.columns, animal_fk_column, link_table)
            link_weight_idx = self._column_index(link_section.columns, "weightrecord_id", link_table)

            used_ids = {row[link_id_idx] for row in link_rows}
            max_id = self._max_int_id(used_ids)
            existing_links = {
                (row[link_animal_idx], row[link_weight_idx])
                for row in link_rows
            }

            link_stores[link_table] = LinkStore(
                table_name=link_table,
                columns=link_section.columns,
                rows=[row[:] for row in link_rows],
                id_idx=link_id_idx,
                animal_fk_idx=link_animal_idx,
                weight_fk_idx=link_weight_idx,
                max_id=max_id,
                used_ids=set(used_ids),
                existing_links=set(existing_links),
            )

        # --- Weights ---
        main_weight_section = main_sections[WEIGHT_TABLE]
        sec_weight_section = secondary_sections[WEIGHT_TABLE]

        main_weight_rows, skipped_main_weights = self._read_section_rows(main_lines, main_weight_section)
        sec_weight_rows, skipped_sec_weights = self._read_section_rows(secondary_lines, sec_weight_section)
        stats["rows_skipped_format"] += skipped_main_weights + skipped_sec_weights

        main_weight_columns = main_weight_section.columns
        sec_weight_columns = sec_weight_section.columns
        if main_weight_columns != sec_weight_columns:
            raise CommandError("Columns mismatch for veterinary_weightrecord between backups.")

        weight_id_idx = self._column_index(main_weight_columns, "id", WEIGHT_TABLE)
        weight_tag_idx = self._column_index(main_weight_columns, "tag_id", WEIGHT_TABLE)
        weight_date_idx = self._column_index(main_weight_columns, "weight_date", WEIGHT_TABLE)
        weight_value_idx = self._column_index(main_weight_columns, "weight", WEIGHT_TABLE)

        merged_weight_rows = [row[:] for row in main_weight_rows]
        used_weight_ids = {row[weight_id_idx] for row in merged_weight_rows}
        max_weight_id = self._max_int_id(used_weight_ids)

        # Natural uniqueness in main by (main_tag_id, date, weight)
        main_weight_natural_to_id: Dict[Tuple[str, str, str], str] = {}
        for row_values in merged_weight_rows:
            natural_key = (
                row_values[weight_tag_idx],
                row_values[weight_date_idx],
                row_values[weight_value_idx],
            )
            if natural_key not in main_weight_natural_to_id:
                main_weight_natural_to_id[natural_key] = row_values[weight_id_idx]

        # For linking
        tag_and_weight_pairs_for_linking: Set[Tuple[str, str]] = set()
        sec_weight_id_to_main_weight_id: Dict[str, str] = {}

        for sec_row in sec_weight_rows:
            stats["secondary_weights_total"] += 1

            sec_weight_id = sec_row[weight_id_idx]
            sec_tag_id = sec_row[weight_tag_idx]
            sec_tag_number = sec_tag_id_to_number.get(sec_tag_id)
            if not sec_tag_number:
                stats["secondary_weights_skipped_no_tag_in_secondary"] += 1
                continue

            main_tag_id = main_tag_number_to_id.get(sec_tag_number)
            if not main_tag_id:
                stats["secondary_weights_skipped_tag_absent_in_main"] += 1
                continue

            stats["secondary_weights_mapped_to_main_tag"] += 1

            natural_key = (
                main_tag_id,
                sec_row[weight_date_idx],
                sec_row[weight_value_idx],
            )
            existing_main_weight_id = main_weight_natural_to_id.get(natural_key)
            if existing_main_weight_id:
                sec_weight_id_to_main_weight_id[sec_weight_id] = existing_main_weight_id
                tag_and_weight_pairs_for_linking.add((main_tag_id, existing_main_weight_id))
                stats["secondary_weights_reused_existing_main"] += 1
                continue

            max_weight_id += 1
            new_weight_id = str(max_weight_id)
            new_row = sec_row[:]
            new_row[weight_id_idx] = new_weight_id
            new_row[weight_tag_idx] = main_tag_id

            merged_weight_rows.append(new_row)
            used_weight_ids.add(new_weight_id)
            main_weight_natural_to_id[natural_key] = new_weight_id
            sec_weight_id_to_main_weight_id[sec_weight_id] = new_weight_id
            tag_and_weight_pairs_for_linking.add((main_tag_id, new_weight_id))
            stats["weights_added"] += 1

        rows_replacements[WEIGHT_TABLE] = merged_weight_rows

        # --- Build links by tag ---
        for main_tag_id, main_weight_id in sorted(tag_and_weight_pairs_for_linking):
            animal_ref = main_tag_id_to_animal_ref.get(main_tag_id)
            if not animal_ref:
                stats["weights_without_animal_in_main"] += 1
                continue

            link_table, animal_id = animal_ref
            link_store = link_stores.get(link_table)
            if not link_store:
                stats["weights_without_animal_in_main"] += 1
                continue

            link_key = (animal_id, main_weight_id)
            if link_key in link_store.existing_links:
                continue

            link_store.max_id += 1
            new_link_id = str(link_store.max_id)
            link_store.used_ids.add(new_link_id)

            new_link_row = [r"\N"] * len(link_store.columns)
            new_link_row[link_store.id_idx] = new_link_id
            new_link_row[link_store.animal_fk_idx] = animal_id
            new_link_row[link_store.weight_fk_idx] = main_weight_id

            link_store.rows.append(new_link_row)
            link_store.existing_links.add(link_key)
            stats["links_added"] += 1

        for table_name, link_store in link_stores.items():
            rows_replacements[table_name] = link_store.rows

        # Apply replacements from bottom to top to keep indices valid.
        for table_name in sorted(
            rows_replacements.keys(),
            key=lambda tbl: main_sections[tbl].data_start,
            reverse=True,
        ):
            section = main_sections[table_name]
            replacement_lines = ["\t".join(row_values) for row_values in rows_replacements[table_name]]
            merged_lines[section.data_start:section.data_end] = replacement_lines

        self._write_sql_lines(output_path, merged_lines)

        self.stdout.write(self.style.SUCCESS("Backup merge completed (weight-only, tag-based)."))
        self.stdout.write(f"Secondary weights total: {stats['secondary_weights_total']}")
        self.stdout.write(f"Secondary weights mapped by tag: {stats['secondary_weights_mapped_to_main_tag']}")
        self.stdout.write(f"Secondary weights reused existing in main: {stats['secondary_weights_reused_existing_main']}")
        self.stdout.write(f"Weights added to main: {stats['weights_added']}")
        self.stdout.write(f"Links added in animals_*_weight_records: {stats['links_added']}")
        self.stdout.write(
            f"Skipped secondary weights (tag id absent in secondary tag table): "
            f"{stats['secondary_weights_skipped_no_tag_in_secondary']}"
        )
        self.stdout.write(
            f"Skipped secondary weights (tag absent in main): "
            f"{stats['secondary_weights_skipped_tag_absent_in_main']}"
        )
        self.stdout.write(f"Weights without resolvable animal in main: {stats['weights_without_animal_in_main']}")
        self.stdout.write(f"Rows skipped (format mismatch): {stats['rows_skipped_format']}")
        self.stdout.write(f"Missing animal/link tables in main: {stats['link_tables_missing_in_main']}")
        self.stdout.write(self.style.SUCCESS(f"Merged backup saved: {output_path}"))

    def _print_backups_list(self, backups_dir: Path):
        backup_files = sorted(
            [p for p in backups_dir.glob("*.sql") if p.is_file()],
            key=lambda p: p.stat().st_ctime,
            reverse=True,
        )
        if not backup_files:
            self.stdout.write(self.style.WARNING("No .sql backups found in backups/."))
            return

        self.stdout.write("Available backups:")
        for idx, backup_file in enumerate(backup_files, start=1):
            size_mb = backup_file.stat().st_size / (1024 * 1024)
            ctime = datetime.fromtimestamp(backup_file.stat().st_ctime).strftime("%Y-%m-%d %H:%M:%S")
            self.stdout.write(f"{idx:2d}. {backup_file.name} | {size_mb:.2f} MB | {ctime}")

    def _resolve_input_path(self, raw_path: str, backups_dir: Path, option_name: str) -> Path:
        candidate = Path(raw_path)
        if candidate.is_file():
            return candidate.resolve()

        backup_candidate = backups_dir / raw_path
        if backup_candidate.is_file():
            return backup_candidate.resolve()

        raise CommandError(
            f"Cannot find {option_name} backup file: {raw_path}. "
            f"Checked: {candidate} and {backup_candidate}"
        )

    def _resolve_output_path(
        self,
        output_raw: Optional[str],
        backups_dir: Path,
        main_path: Path,
        secondary_path: Path,
    ) -> Path:
        if output_raw:
            output_path = Path(output_raw)
            if not output_path.is_absolute():
                output_path = backups_dir / output_path
            output_path.parent.mkdir(parents=True, exist_ok=True)
            return output_path.resolve()

        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        auto_name = f"merged_weights_{main_path.stem}__{secondary_path.stem}__{timestamp}.sql"
        return (backups_dir / auto_name).resolve()

    def _read_sql_lines(self, path: Path) -> List[str]:
        try:
            with open(path, "r", encoding="utf-8") as file_obj:
                return file_obj.read().splitlines()
        except UnicodeDecodeError:
            with open(path, "r", encoding="cp1251") as file_obj:
                return file_obj.read().splitlines()

    def _write_sql_lines(self, path: Path, lines: List[str]):
        content = "\n".join(lines) + "\n"
        with open(path, "w", encoding="utf-8", newline="\n") as file_obj:
            file_obj.write(content)

    def _parse_copy_sections(self, lines: List[str]) -> Dict[str, CopySection]:
        sections: Dict[str, CopySection] = {}
        line_idx = 0
        total_lines = len(lines)

        while line_idx < total_lines:
            current_line = lines[line_idx]
            match = COPY_HEADER_RE.match(current_line)
            if not match:
                line_idx += 1
                continue

            table_name = match.group(1)
            columns = [col.strip().strip('"') for col in match.group(2).split(",")]
            data_start = line_idx + 1

            data_end = data_start
            while data_end < total_lines and lines[data_end] != r"\.":
                data_end += 1

            if data_end >= total_lines:
                raise CommandError(f"Malformed COPY section for table {table_name}: missing \\.")

            if table_name in sections:
                raise CommandError(f"Duplicate COPY section for table {table_name} detected.")

            sections[table_name] = CopySection(
                table_name=table_name,
                columns=columns,
                data_start=data_start,
                data_end=data_end,
            )

            line_idx = data_end + 1

        return sections

    def _read_section_rows(
        self,
        lines: List[str],
        section: CopySection,
    ) -> Tuple[List[List[str]], int]:
        rows: List[List[str]] = []
        skipped_rows = 0

        for line_idx in range(section.data_start, section.data_end):
            raw_line = lines[line_idx]
            row_values = raw_line.split("\t")
            if len(row_values) != len(section.columns):
                skipped_rows += 1
                continue
            rows.append(row_values)

        return rows, skipped_rows

    def _column_index(self, columns: List[str], column_name: str, table_name: str) -> int:
        try:
            return columns.index(column_name)
        except ValueError:
            raise CommandError(f"Column '{column_name}' not found in table {table_name}")

    def _max_int_id(self, ids: Set[str]) -> int:
        max_id = 0
        for raw_id in ids:
            try:
                parsed_id = int(raw_id)
            except (TypeError, ValueError):
                continue
            if parsed_id > max_id:
                max_id = parsed_id
        return max_id

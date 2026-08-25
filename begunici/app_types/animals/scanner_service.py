import re
import time
from dataclasses import dataclass
from datetime import datetime

import requests
from django.conf import settings
from django.db.models import Q
from django.urls import reverse

from begunici.app_types.animals.models import Ewe, Maker, Ram, Sheep


VID = 0x28E9
PID = 0x028B
REPORT_OUT = 0x03
MAX_HISTORY_RECORDS = 256
DEFAULT_SCANNER_AGENT_URL = "http://host.docker.internal:8765/read"

BASE36_ALPHABET = "0123456789abcdefghijklmnopqrstuvwxyz"
DIGITAL_CHIP_RE = re.compile(r"^\d{15}$")

ANIMAL_TYPES = (
    ("maker", "Баран-Производитель", Maker, "animals:maker-detail"),
    ("ram", "Баранчик", Ram, "animals:ram-detail"),
    ("ewe", "Ярка", Ewe, "animals:ewe-detail"),
    ("sheep", "Овцематка", Sheep, "animals:sheep-detail"),
)


class ScannerError(RuntimeError):
    """Понятная для интерфейса ошибка чтения сканера."""


class RfidConversionError(ValueError):
    """Ошибка проверки или преобразования цифрового номера чипа."""


@dataclass(frozen=True)
class ScannerHistoryRecord:
    index: int
    chip: str
    scanner_timestamp: str


@dataclass(frozen=True)
class RfidConversionResult:
    digital_id: str
    rshn_tag: str
    warning: str | None = None


def calculate_checksum(value, base):
    if base not in {5, 10}:
        raise ValueError("Основание контрольной суммы должно быть 5 или 10")

    total = 0
    for position, character in enumerate(value, start=1):
        symbol_value = ord(character) - 48
        if position % 2 == 0:
            symbol_value *= 2
            if symbol_value > 9:
                symbol_value -= 9
        total += symbol_value

    remainder = total % base
    return 0 if remainder == 0 else base - remainder


def _to_base36(number):
    if number == 0:
        return "0"

    digits = []
    while number:
        number, remainder = divmod(number, 36)
        digits.append(BASE36_ALPHABET[remainder])
    return "".join(reversed(digits))


def digital_chip_to_rshn(digital_id):
    normalized = str(digital_id or "").strip()
    if not DIGITAL_CHIP_RE.fullmatch(normalized):
        raise RfidConversionError("Номер чипа должен содержать ровно 15 цифр")
    if not normalized.startswith("643"):
        raise RfidConversionError("Номер чипа должен начинаться с кода страны 643")

    encoded_check_digit = int(normalized[3])
    unique_decimal = normalized[4:]
    base_check_digit = calculate_checksum(unique_decimal, 5)
    is_group = encoded_check_digit >= 5
    expected_check_digit = base_check_digit + (5 if is_group else 0)

    warning = None
    if encoded_check_digit != expected_check_digit:
        warning = (
            "Контрольная цифра чипа не совпадает: "
            f"{encoded_check_digit}, должна быть {expected_check_digit}"
        )

    unique_base36 = _to_base36(int(unique_decimal))
    if len(unique_base36) > 7:
        raise RfidConversionError(
            "Уникальная часть чипа не помещается в федеральный формат"
        )
    unique_base36 = unique_base36.rjust(7, "0")

    type_digit = "2" if is_group else "1"
    rshn_body = f"RU{type_digit}{unique_base36}"
    rshn_tag = f"{rshn_body}{calculate_checksum(rshn_body, 10)}"

    return RfidConversionResult(
        digital_id=normalized,
        rshn_tag=rshn_tag,
        warning=warning,
    )


def _hx(data):
    return " ".join(f"{byte:02X}" for byte in data)


def _load_hid_module():
    try:
        import hid
    except ImportError as exc:
        raise ScannerError(
            "Библиотека для работы со сканером не установлена"
        ) from exc
    return hid


def _find_mi03_device_path(hid):
    for device_info in hid.enumerate(VID, PID):
        path = device_info.get("path")
        if isinstance(path, str):
            path_bytes = path.encode(errors="ignore")
        else:
            path_bytes = path or b""

        if b"MI_03" in path_bytes.upper():
            return path
    return None


def _receive(dev, timeout=0.8):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            data = dev.read(64)
        except Exception as exc:
            raise ScannerError(f"Ошибка чтения данных со сканера: {exc}") from exc

        if data:
            return bytes(data)

        time.sleep(0.002)

    return None


def _read_record(dev, index):
    packet = bytearray(64)
    packet[0] = REPORT_OUT
    packet[1] = 0x02
    packet[2] = 0x02
    packet[3] = 0x00
    packet[4] = index

    try:
        dev.write(list(packet))
    except Exception as exc:
        raise ScannerError(f"Ошибка отправки запроса сканеру: {exc}") from exc

    return _receive(dev)


def parse_history_record(rx, index):
    if not rx:
        return None

    if len(rx) < 3:
        raise ValueError(f"Слишком короткий ответ сканера: {_hx(rx)}")

    if rx[0] != 0x04:
        raise ValueError(f"Неожиданный report ID: {rx[0]:02X}")

    if rx[1] != 0x02:
        raise ValueError(f"Неожиданная команда: {rx[1]:02X}")

    payload_len = rx[2]
    payload = rx[3:3 + payload_len]

    if payload_len != 46:
        raise ValueError(f"Неожиданная длина payload: {payload_len}")

    if len(payload) != payload_len:
        raise ValueError("Ответ сканера обрезан")

    chip = payload[3:18].decode("ascii", errors="strict")
    timestamp = payload[19:38].decode("ascii", errors="strict")

    if not DIGITAL_CHIP_RE.fullmatch(chip):
        raise ValueError(f"Некорректный номер чипа: {chip!r}")

    datetime.strptime(timestamp, "%Y/%m/%d %H:%M:%S")

    return ScannerHistoryRecord(index=index, chip=chip, scanner_timestamp=timestamp)


def _read_scanner_history_hid(max_records=MAX_HISTORY_RECORDS):
    hid = _load_hid_module()
    path = _find_mi03_device_path(hid)
    if path is None:
        raise ScannerError(
            "Сканер DEJ-380 не найден"
        )

    dev = hid.device()
    records = []
    warnings = []

    try:
        dev.open_path(path)
        dev.set_nonblocking(True)

        for index in range(max_records):
            rx = _read_record(dev, index)
            if not rx:
                break
            if b"ERRoR" in rx:
                break

            try:
                record = parse_history_record(rx, index)
            except Exception as exc:
                warnings.append(f"Запись #{index + 1} пропущена: {exc}")
                time.sleep(0.05)
                continue

            if record:
                records.append(record)
            time.sleep(0.05)
    except ScannerError:
        raise
    except Exception as exc:
        raise ScannerError(f"Не удалось открыть или прочитать сканер: {exc}") from exc
    finally:
        try:
            dev.close()
        except Exception:
            pass

    return records, warnings


def _scanner_agent_url():
    configured_url = getattr(settings, "SCANNER_AGENT_URL", None)
    if configured_url is not None:
        return str(configured_url).strip()
    return DEFAULT_SCANNER_AGENT_URL


def _read_scanner_history_agent(max_records=MAX_HISTORY_RECORDS):
    agent_url = _scanner_agent_url()
    if not agent_url:
        raise ScannerError("Локальный мост сканера не настроен.")

    try:
        response = requests.get(
            agent_url,
            params={"max_records": max_records},
            timeout=35,
        )
    except requests.RequestException as exc:
        raise ScannerError(
            "Сканер не отвечает"
        ) from exc

    try:
        payload = response.json()
    except ValueError as exc:
        raise ScannerError("Сканер вернул некорректный ответ") from exc

    if response.status_code >= 400:
        raise ScannerError(payload.get("error") or "Сканер не прочитал данные.")

    raw_records = payload.get("records") or payload.get("results") or []
    if not isinstance(raw_records, list):
        raise ScannerError("Сканер вернул записи в некорректном формате")

    records = []
    for item in raw_records:
        if not isinstance(item, dict):
            continue
        chip = str(item.get("chip") or item.get("id") or "").strip()
        if not DIGITAL_CHIP_RE.fullmatch(chip):
            continue
        try:
            index = int(item.get("index") or len(records))
        except (TypeError, ValueError):
            index = len(records)
        scanner_timestamp = str(
            item.get("scanner_timestamp") or item.get("timestamp") or ""
        )
        records.append(
            ScannerHistoryRecord(
                index=index,
                chip=chip,
                scanner_timestamp=scanner_timestamp,
            )
        )

    warnings = payload.get("warnings") or []
    if not isinstance(warnings, list):
        warnings = [str(warnings)]

    return records, warnings


def read_scanner_history(max_records=MAX_HISTORY_RECORDS):
    errors = []

    try:
        return _read_scanner_history_hid(max_records=max_records)
    except ScannerError as exc:
        errors.append(str(exc))

    agent_url = _scanner_agent_url()
    if agent_url:
        try:
            return _read_scanner_history_agent(max_records=max_records)
        except ScannerError as exc:
            errors.append(f"Локальный мост: {exc}")

    raise ScannerError(" ".join(errors))


def _animal_link_payload(type_key, type_label, route_name, animal):
    tag_number = animal.tag.tag_number if animal.tag else ""
    return {
        "tag_number": tag_number,
        "display_name": tag_number,
        "animal_type": type_key,
        "animal_type_label": type_label,
        "url": reverse(route_name, kwargs={"tag_number": tag_number}),
        "is_archived": bool(animal.is_archived),
    }


def find_animals_by_chip(chip):
    candidates = {str(chip or "").strip()}
    conversion_warning = None

    try:
        conversion = digital_chip_to_rshn(chip)
        candidates.add(conversion.rshn_tag)
        conversion_warning = conversion.warning
    except RfidConversionError as exc:
        conversion_warning = str(exc)

    animals = []
    for type_key, type_label, model, route_name in ANIMAL_TYPES:
        search_query = Q(tag__tag_number__iexact=str(chip or "").strip())
        for candidate in candidates:
            if candidate:
                search_query |= Q(rshn_tag__iexact=candidate)

        queryset = (
            model.objects.select_related("tag")
            .filter(search_query)
            .order_by("tag__tag_number")
        )
        for animal in queryset:
            animals.append(_animal_link_payload(type_key, type_label, route_name, animal))

    return animals, conversion_warning


def build_scanner_rows(records):
    rows = []
    warnings = []

    for record in records:
        animals, _warning = find_animals_by_chip(record.chip)

        rows.append(
            {
                "index": record.index,
                "chip": record.chip,
                "scanner_timestamp": record.scanner_timestamp,
                "animals": animals,
                "tag_display": ", ".join(item["display_name"] for item in animals),
            }
        )

    return rows, warnings

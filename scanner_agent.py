import argparse
import json
import re
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse


VID = 0x28E9
PID = 0x028B
REPORT_OUT = 0x03
MAX_HISTORY_RECORDS = 256
DIGITAL_CHIP_RE = re.compile(r"^\d{15}$")


class ScannerError(RuntimeError):
    pass


@dataclass(frozen=True)
class ScannerHistoryRecord:
    index: int
    chip: str
    scanner_timestamp: str


def hx(data):
    return " ".join(f"{byte:02X}" for byte in data)


def load_hid_module():
    try:
        import hid
    except ImportError as exc:
        raise ScannerError(
            "Библиотека hidapi не установлена в Python, где запущен scanner_agent.py."
        ) from exc
    return hid


def find_mi03_device_path(hid):
    for device_info in hid.enumerate(VID, PID):
        path = device_info.get("path")
        if isinstance(path, str):
            path_bytes = path.encode(errors="ignore")
        else:
            path_bytes = path or b""

        if b"MI_03" in path_bytes.upper():
            return path
    return None


def receive(dev, timeout=0.8):
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


def read_record(dev, index):
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

    return receive(dev)


def parse_history_record(rx, index):
    if not rx:
        return None

    if len(rx) < 3:
        raise ValueError(f"Слишком короткий ответ сканера: {hx(rx)}")
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


def read_scanner_history(max_records=MAX_HISTORY_RECORDS):
    hid = load_hid_module()
    path = find_mi03_device_path(hid)
    if path is None:
        raise ScannerError(
            "Сканер DEJ-380 не найден в Windows. Проверьте подключение устройства."
        )

    dev = hid.device()
    records = []
    warnings = []

    try:
        dev.open_path(path)
        dev.set_nonblocking(True)

        for index in range(max_records):
            rx = read_record(dev, index)
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
    finally:
        try:
            dev.close()
        except Exception:
            pass

    return records, warnings


class ScannerAgentHandler(BaseHTTPRequestHandler):
    server_version = "BeguniciScannerAgent/1.0"

    def _json_response(self, status_code, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed_url = urlparse(self.path)
        if parsed_url.path == "/health":
            self._json_response(200, {"ok": True})
            return

        if parsed_url.path != "/read":
            self._json_response(404, {"error": "Неизвестный URL"})
            return

        query = parse_qs(parsed_url.query)
        try:
            max_records = int((query.get("max_records") or [MAX_HISTORY_RECORDS])[0])
        except (TypeError, ValueError):
            max_records = MAX_HISTORY_RECORDS
        max_records = max(1, min(max_records, MAX_HISTORY_RECORDS))

        try:
            records, warnings = read_scanner_history(max_records=max_records)
        except ScannerError as exc:
            self._json_response(400, {"error": str(exc), "warnings": []})
            return
        except Exception as exc:
            self._json_response(500, {"error": f"Ошибка моста сканера: {exc}", "warnings": []})
            return

        self._json_response(
            200,
            {
                "records": [asdict(record) for record in records],
                "warnings": warnings,
            },
        )

    def log_message(self, format, *args):
        return


def main():
    parser = argparse.ArgumentParser(description="Локальный мост DEJ-380 для Docker.")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()

    server = ThreadingHTTPServer((args.host, args.port), ScannerAgentHandler)
    print(f"Scanner agent started: http://{args.host}:{args.port}/read")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()

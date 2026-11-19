"""Reading and writing data files.

patients.csv      one row per patient
appointments.json list of appointment records (booked and cancelled)
doctors.json      list of doctors

Writes go to a temporary file first and then replace the real file,
so a crash halfway through never leaves a half-written file.
"""
import csv
import io
import json
import os
import tempfile
from pathlib import Path

from config import DEFAULT_DOCTORS
from errors import StorageError

PATIENT_FIELDS = ["patient_id", "name", "age", "gender", "phone", "registered_on"]


def _atomic_write(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=path.name, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
            f.write(text)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise


def _read_json(path: Path, default):
    if not path.exists():
        return default
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        raise StorageError(f"{path.name} is corrupted (line {e.lineno}). Fix or delete it, then restart.") from e
    except OSError as e:
        raise StorageError(f"Could not read {path.name}: {e}") from e


def load_patients(path: Path) -> dict:
    """Returns {patient_id: record}."""
    if not path.exists():
        return {}
    patients = {}
    try:
        with open(path, encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                if not row.get("patient_id"):
                    continue
                row["age"] = int(row["age"])
                patients[row["patient_id"]] = row
    except (OSError, ValueError, KeyError) as e:
        raise StorageError(f"{path.name} could not be read: {e}") from e
    return patients


def save_patients(path: Path, patients: dict):
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=PATIENT_FIELDS)
    writer.writeheader()
    for p in patients.values():
        writer.writerow({k: p[k] for k in PATIENT_FIELDS})
    _atomic_write(path, buf.getvalue())


def load_appointments(path: Path) -> list:
    data = _read_json(path, [])
    if not isinstance(data, list):
        raise StorageError(f"{path.name} must contain a JSON list.")
    return data


def save_appointments(path: Path, appointments: list):
    _atomic_write(path, json.dumps(appointments, indent=2))


def load_doctors(path: Path) -> dict:
    """Returns {doctor_id: record}. Creates doctors.json from config on first run."""
    if not path.exists():
        _atomic_write(path, json.dumps(DEFAULT_DOCTORS, indent=2))
    data = _read_json(path, [])
    return {d["doctor_id"]: d for d in data}

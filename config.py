"""Settings for CareQueue. Change these to match your hospital's OPD timings."""
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"

# OPD runs from SLOT_START to SLOT_END, split into SLOT_MINUTES slots.
SLOT_START = "09:00"
SLOT_END = "13:00"
SLOT_MINUTES = 15

# How far ahead patients can book.
BOOKING_WINDOW_DAYS = 30

# Weekday numbers: Monday = 0 ... Sunday = 6
WEEKDAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

# Used to create data/doctors.json the first time the app runs.
DEFAULT_DOCTORS = [
    {"doctor_id": "D01", "name": "Dr. Ananya Rao", "department": "General Medicine", "working_days": [0, 1, 2, 3, 4, 5]},
    {"doctor_id": "D02", "name": "Dr. Vikram Shah", "department": "General Medicine", "working_days": [0, 2, 4]},
    {"doctor_id": "D03", "name": "Dr. Meera Iyer", "department": "Cardiology", "working_days": [0, 1, 3, 4]},
    {"doctor_id": "D04", "name": "Dr. Arjun Menon", "department": "Orthopaedics", "working_days": [1, 2, 4, 5]},
    {"doctor_id": "D05", "name": "Dr. Kavya Nair", "department": "Paediatrics", "working_days": [0, 1, 2, 3, 4, 5]},
    {"doctor_id": "D06", "name": "Dr. Rahul Verma", "department": "Dermatology", "working_days": [1, 3, 5]},
    {"doctor_id": "D07", "name": "Dr. Sneha Pillai", "department": "ENT", "working_days": [0, 2, 3, 5]},
]

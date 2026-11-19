"""Input checks for form data. Each function returns clean values or raises ValidationError."""
import re
from datetime import date, datetime, timedelta

from config import BOOKING_WINDOW_DAYS
from errors import ValidationError

NAME_RE = re.compile(r"^[A-Za-z][A-Za-z .'-]{1,59}$")
PHONE_RE = re.compile(r"^[6-9]\d{9}$")  # 10-digit Indian mobile number
PATIENT_ID_RE = re.compile(r"^P\d{4,}$")
GENDERS = {"Male", "Female", "Other"}


def clean_patient(form):
    """Validate the registration form. Returns a dict with name, age, gender, phone."""
    name = " ".join((form.get("name") or "").split())
    if not NAME_RE.match(name):
        raise ValidationError("Name must be 2-60 letters (spaces, dots, apostrophes and hyphens allowed).")

    age_text = (form.get("age") or "").strip()
    if not age_text.isdigit() or not 0 <= int(age_text) <= 120:
        raise ValidationError("Age must be a whole number from 0 to 120.")

    gender = (form.get("gender") or "").strip()
    if gender not in GENDERS:
        raise ValidationError("Choose a gender: Male, Female or Other.")

    phone = re.sub(r"[\s-]", "", form.get("phone") or "")
    if phone.startswith("+91"):
        phone = phone[3:]
    if not PHONE_RE.match(phone):
        raise ValidationError("Phone must be a 10-digit mobile number starting with 6, 7, 8 or 9.")

    return {"name": name.title(), "age": int(age_text), "gender": gender, "phone": phone}


def clean_patient_id(value):
    pid = (value or "").strip().upper()
    if not PATIENT_ID_RE.match(pid):
        raise ValidationError("Patient ID looks like P0001.")
    return pid


def parse_date(value):
    """Turn 'YYYY-MM-DD' into a date."""
    try:
        return datetime.strptime((value or "").strip(), "%Y-%m-%d").date()
    except ValueError:
        raise ValidationError("Date must be in YYYY-MM-DD format.") from None


def check_booking_date(day, today=None):
    """Bookings are allowed from today up to BOOKING_WINDOW_DAYS ahead."""
    today = today or date.today()
    if day < today:
        raise ValidationError("You cannot book an appointment in the past.")
    if day > today + timedelta(days=BOOKING_WINDOW_DAYS):
        raise ValidationError(f"Bookings open only {BOOKING_WINDOW_DAYS} days ahead.")

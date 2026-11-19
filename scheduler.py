"""Core booking logic: slot availability, token numbers and clash checks.

Data structures
---------------
self.patients  : {patient_id: {...}}                              patient records dictionary
self.schedule  : {doctor_id: {date: {slot: appointment_id}}}      doctor schedule (nested dictionary)
self.appointments : [ {...}, ... ]                                every appointment, booked or cancelled

The schedule holds only *booked* slots, so a slot is free when it is missing from
schedule[doctor][date].
"""
import threading
from datetime import date, datetime, timedelta
from pathlib import Path

import config
from errors import (
    AppointmentNotFoundError,
    DoubleBookingError,
    InvalidDoctorError,
    InvalidPatientError,
    SlotFullError,
    ValidationError,
)
from storage import (
    load_appointments,
    load_doctors,
    load_patients,
    save_appointments,
    save_patients,
)
from validation import check_booking_date, clean_patient, clean_patient_id, parse_date


def all_slots():
    """Every slot start time in a day, e.g. ['09:00', '09:15', ...]."""
    start = datetime.strptime(config.SLOT_START, "%H:%M")
    end = datetime.strptime(config.SLOT_END, "%H:%M")
    step = timedelta(minutes=config.SLOT_MINUTES)
    slots = []
    while start + step <= end:
        slots.append(start.strftime("%H:%M"))
        start += step
    return slots


SLOTS = all_slots()


class CareQueue:
    def __init__(self, data_dir=None):
        data_dir = Path(data_dir or config.DATA_DIR)
        self.patients_path = data_dir / "patients.csv"
        self.appointments_path = data_dir / "appointments.json"
        self.doctors_path = data_dir / "doctors.json"
        # Flask serves requests on several threads; one lock keeps check-then-book atomic.
        self.lock = threading.RLock()
        self.doctors = load_doctors(self.doctors_path)
        self.patients = load_patients(self.patients_path)
        self.appointments = load_appointments(self.appointments_path)
        self.schedule = self._build_schedule()
        # Bulk scripts (seed_data.py) turn this off and call save_all() once at the end.
        self.autosave = True

    def _save(self, patients=False, appointments=False):
        if not self.autosave:
            return
        if patients:
            save_patients(self.patients_path, self.patients)
        if appointments:
            save_appointments(self.appointments_path, self.appointments)

    def save_all(self):
        with self.lock:
            save_patients(self.patients_path, self.patients)
            save_appointments(self.appointments_path, self.appointments)

    # ---------- lookups ----------

    def _build_schedule(self):
        schedule = {doctor_id: {} for doctor_id in self.doctors}
        for a in self.appointments:
            if a["status"] == "booked":
                schedule.setdefault(a["doctor_id"], {}).setdefault(a["date"], {})[a["slot"]] = a["appointment_id"]
        return schedule

    def get_patient(self, patient_id):
        pid = clean_patient_id(patient_id)
        if pid not in self.patients:
            raise InvalidPatientError(f"No patient with ID {pid}. Register the patient first.")
        return self.patients[pid]

    def get_doctor(self, doctor_id):
        if doctor_id not in self.doctors:
            raise InvalidDoctorError("Choose a doctor from the list.")
        return self.doctors[doctor_id]

    def get_appointment(self, appointment_id):
        for a in self.appointments:
            if a["appointment_id"] == appointment_id:
                return a
        raise AppointmentNotFoundError(f"No appointment with ID {appointment_id}.")

    def works_on(self, doctor_id, day: date):
        return day.weekday() in self.get_doctor(doctor_id)["working_days"]

    def find_patients(self, query):
        """Search by patient ID, name or phone."""
        q = (query or "").strip().lower()
        rows = list(self.patients.values())
        if q:
            rows = [p for p in rows if q in p["patient_id"].lower() or q in p["name"].lower() or q in p["phone"]]
        return sorted(rows, key=lambda p: p["patient_id"], reverse=True)

    # ---------- core logic ----------

    def available_slots(self, doctor_id, date_str, now=None):
        """Free slots for a doctor on a date. Past slots today are not offered."""
        day = parse_date(date_str)
        if not self.works_on(doctor_id, day):
            return []
        taken = self.schedule.get(doctor_id, {}).get(day.isoformat(), {})
        free = [s for s in SLOTS if s not in taken]
        now = now or datetime.now()
        if day == now.date():
            free = [s for s in free if s > now.strftime("%H:%M")]
        return free

    def next_token(self, doctor_id, date_str):
        """Tokens run 1, 2, 3... per doctor per day. Cancelled tokens are not reused,
        so a token number always refers to one appointment."""
        used = [
            a["token"] for a in self.appointments
            if a["doctor_id"] == doctor_id and a["date"] == date_str
        ]
        return max(used, default=0) + 1

    def check_clash(self, patient_id, doctor_id, date_str, slot):
        """Raise if this booking would clash with an existing one."""
        day_schedule = self.schedule.get(doctor_id, {}).get(date_str, {})
        if len(day_schedule) >= len(SLOTS):
            raise SlotFullError(f"{self.doctors[doctor_id]['name']} has no slots left on {date_str}.")
        if slot in day_schedule:
            raise SlotFullError(f"The {slot} slot is already booked. Pick another slot.")
        for a in self.appointments:
            if a["status"] != "booked" or a["patient_id"] != patient_id or a["date"] != date_str:
                continue
            if a["doctor_id"] == doctor_id:
                raise DoubleBookingError(
                    f"This patient already has token {a['token']} with this doctor at {a['slot']} on {date_str}."
                )
            if a["slot"] == slot:
                other = self.doctors.get(a["doctor_id"], {}).get("name", a["doctor_id"])
                raise DoubleBookingError(f"This patient is already seeing {other} at {slot} on {date_str}.")

    # ---------- actions ----------

    def register_patient(self, form, registered_on=None):
        data = clean_patient(form)
        with self.lock:
            for p in self.patients.values():
                if p["phone"] == data["phone"] and p["name"].lower() == data["name"].lower():
                    raise ValidationError(f"{p['name']} is already registered as {p['patient_id']}.")
            numbers = [int(pid[1:]) for pid in self.patients]
            pid = f"P{max(numbers, default=0) + 1:04d}"
            record = {"patient_id": pid, **data, "registered_on": (registered_on or date.today()).isoformat()}
            self.patients[pid] = record
            self._save(patients=True)
        return record

    def book(self, patient_id, doctor_id, date_str, slot, now=None, allow_past=False):
        """Book a slot and return the appointment. allow_past is only for seeding sample data."""
        now = now or datetime.now()
        patient = self.get_patient(patient_id)
        doctor = self.get_doctor(doctor_id)
        day = parse_date(date_str)
        date_str = day.isoformat()
        if not allow_past:
            check_booking_date(day, now.date())
        if not self.works_on(doctor_id, day):
            raise ValidationError(f"{doctor['name']} does not hold OPD on {config.WEEKDAY_NAMES[day.weekday()]}s.")
        if slot not in SLOTS:
            raise ValidationError("Choose a valid time slot.")
        if not allow_past and day == now.date() and slot <= now.strftime("%H:%M"):
            raise ValidationError("That slot has already passed today.")

        with self.lock:
            self.check_clash(patient["patient_id"], doctor_id, date_str, slot)
            appt = {
                "appointment_id": f"A{len(self.appointments) + 1:05d}",
                "token": self.next_token(doctor_id, date_str),
                "patient_id": patient["patient_id"],
                "doctor_id": doctor_id,
                "department": doctor["department"],
                "date": date_str,
                "slot": slot,
                "status": "booked",
                "booked_at": now.isoformat(timespec="seconds"),
                "cancelled_at": None,
            }
            self.appointments.append(appt)
            self.schedule.setdefault(doctor_id, {}).setdefault(date_str, {})[slot] = appt["appointment_id"]
            self._save(appointments=True)
        return appt

    def cancel(self, appointment_id, now=None):
        with self.lock:
            appt = self.get_appointment(appointment_id)
            if appt["status"] != "booked":
                raise AppointmentNotFoundError(f"Appointment {appointment_id} is already cancelled.")
            appt["status"] = "cancelled"
            appt["cancelled_at"] = (now or datetime.now()).isoformat(timespec="seconds")
            self.schedule[appt["doctor_id"]][appt["date"]].pop(appt["slot"], None)
            self._save(appointments=True)
        return appt

    # ---------- views ----------

    def doctor_day(self, doctor_id, date_str):
        """One row per slot for a doctor's day, with the patient if booked."""
        self.get_doctor(doctor_id)
        day = parse_date(date_str).isoformat()
        taken = self.schedule.get(doctor_id, {}).get(day, {})
        by_id = {a["appointment_id"]: a for a in self.appointments}
        rows = []
        for slot in SLOTS:
            appt = by_id.get(taken.get(slot))
            rows.append({
                "slot": slot,
                "appointment": appt,
                "patient": self.patients.get(appt["patient_id"]) if appt else None,
            })
        return rows

    def list_appointments(self, date_str=None, doctor_id=None, status=None, patient_id=None):
        rows = self.appointments
        if date_str:
            rows = [a for a in rows if a["date"] == date_str]
        if doctor_id:
            rows = [a for a in rows if a["doctor_id"] == doctor_id]
        if status:
            rows = [a for a in rows if a["status"] == status]
        if patient_id:
            rows = [a for a in rows if a["patient_id"] == patient_id]
        return sorted(rows, key=lambda a: (a["date"], a["slot"], a["doctor_id"]), reverse=True)

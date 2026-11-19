"""Fill data/ with sample patients and four weeks of appointments so the analysis has something to show.

    python seed_data.py            # refuses to overwrite existing data
    python seed_data.py --reset    # deletes existing patients and appointments first
"""
import random
import sys
from datetime import date, datetime, timedelta

import config
from errors import CareQueueError
from scheduler import SLOTS, CareQueue

FIRST = ["Aarav", "Diya", "Rohan", "Ishita", "Karthik", "Lakshmi", "Manoj", "Nisha", "Pranav", "Riya",
         "Sanjay", "Tanvi", "Uday", "Varsha", "Yash", "Zoya", "Harish", "Gayathri", "Farhan", "Divya",
         "Arjun", "Bhavna", "Chetan", "Esha", "Gopal", "Hema", "Imran", "Jaya", "Kiran", "Lalitha"]
LAST = ["Sharma", "Iyer", "Reddy", "Khan", "Patel", "Nair", "Gupta", "Das", "Menon", "Singh",
        "Kumar", "Joshi", "Rao", "Pillai", "Bose", "Mehta", "Naidu", "Chopra"]

# Mondays are busiest and late morning is the peak, which gives the charts a realistic shape.
WEEKDAY_WEIGHT = {0: 1.0, 1: 0.8, 2: 0.7, 3: 0.75, 4: 0.65, 5: 0.55}
HOUR_WEIGHT = {9: 0.6, 10: 1.0, 11: 0.9, 12: 0.5}


def seed(days_back=28, days_ahead=5, n_patients=90, seed_value=7):
    rng = random.Random(seed_value)
    today = date.today()
    start = today - timedelta(days=days_back)

    data_dir = config.DATA_DIR
    if "--reset" in sys.argv:
        for name in ("patients.csv", "appointments.json"):
            (data_dir / name).unlink(missing_ok=True)
    cq = CareQueue(data_dir)
    if cq.patients or cq.appointments:
        sys.exit("data/ already has patients or appointments. Run with --reset to replace them.")
    cq.autosave = False

    for _ in range(n_patients):
        first, last = rng.choice(FIRST), rng.choice(LAST)
        cq.register_patient(
            {
                "name": f"{first} {last}",
                "age": str(rng.choice([rng.randint(1, 12), rng.randint(18, 45), rng.randint(46, 85)])),
                "gender": rng.choice(["Male", "Female"]),
                "phone": f"{rng.choice('6789')}{rng.randint(0, 999_999_999):09d}",
            },
            registered_on=start + timedelta(days=rng.randint(0, days_back // 2)),
        )
    patient_ids = list(cq.patients)
    # A fifth of patients visit often, so repeat-visitor analysis has results.
    regulars = patient_ids[: n_patients // 5]

    booked = cancelled = 0
    day = start
    while day <= today + timedelta(days=days_ahead):
        for doctor_id in cq.doctors:
            if not cq.works_on(doctor_id, day):
                continue
            future = day >= today
            target = int(len(SLOTS) * WEEKDAY_WEIGHT[day.weekday()] * rng.uniform(0.45, 0.8) * (0.5 if future else 1))
            slots = [s for s in SLOTS if rng.random() < HOUR_WEIGHT[int(s[:2])]]
            rng.shuffle(slots)
            for slot in slots[:target]:
                pid = rng.choice(regulars) if rng.random() < 0.35 else rng.choice(patient_ids)
                booked_at = datetime.combine(day - timedelta(days=rng.randint(1, 6)), datetime.min.time()) + timedelta(hours=rng.randint(8, 20))
                try:
                    appt = cq.book(pid, doctor_id, day.isoformat(), slot, now=booked_at, allow_past=True)
                except CareQueueError:
                    continue  # clash with the patient's other booking; skip it like a real desk would
                booked += 1
                if rng.random() < 0.07:
                    cq.cancel(appt["appointment_id"], now=booked_at + timedelta(hours=rng.randint(1, 48)))
                    cancelled += 1
        day += timedelta(days=1)

    cq.save_all()
    print(f"Created {len(cq.patients)} patients and {booked} appointments ({cancelled} cancelled) in {data_dir}.")


if __name__ == "__main__":
    seed()

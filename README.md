# CareQueue: Hospital OPD Appointments and Patient Records

A Flask website that registers patients, books and cancels OPD appointments by doctor, date and time slot, issues token numbers, prevents double booking, and shows pandas analysis with matplotlib charts.

## Run it

```bash
cd carequeue
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python seed_data.py              # optional: sample patients and 4 weeks of appointments
python app.py
```

Open http://127.0.0.1:5000.

`python seed_data.py --reset` wipes patients and appointments and creates fresh sample data.

## Pages

| Page | What it does |
|------|--------------|
| Dashboard | Today's appointments, each doctor's load, the next patients in the queue |
| Patients | Register a patient (validated form), search by name, ID or phone, view history |
| Book | Pick a patient, doctor and date; only free slots are offered; issues a token |
| Appointments | Filter by date, doctor, status or patient; cancel an appointment |
| Doctor's day | Slot-by-slot view of one doctor's day; free slots link straight to booking |
| Analysis | Department load, daily trend, busiest hours and weekdays, repeat patients |

## How the brief maps to the code

| Requirement | Where |
|-------------|-------|
| Menu, input and validation | Navigation bar in `templates/base.html`; checks in `validation.py` |
| Slot availability, tokens, clash checks | `available_slots`, `next_token`, `check_clash` in `scheduler.py` |
| Doctor schedule as nested dictionary | `CareQueue.schedule`: `{doctor_id: {date: {slot: appointment_id}}}` |
| Patient records dictionary | `CareQueue.patients`: `{patient_id: record}` |
| Patients in CSV, appointments in JSON | `storage.py` → `data/patients.csv`, `data/appointments.json` |
| Exceptions for full slots / invalid patient ID | `SlotFullError`, `InvalidPatientError` and others in `errors.py` |
| pandas analysis | `analysis.py` |
| Bar, line and hour-wise heat-style bar charts | `charts.py`, served at `/charts/<name>.png` |

## Booking rules

- OPD runs 09:00–13:00 in 15-minute slots (16 per doctor per day). Change this in `config.py`.
- Each doctor works set weekdays (`data/doctors.json`, created from `config.py` on first run).
- Bookings are allowed from today up to 30 days ahead. Slots that have already passed today are not offered.
- Tokens run 1, 2, 3… per doctor per day. A cancelled token is not reused.
- A booking is refused when the slot is taken, the doctor's day is full, the patient already has an appointment with that doctor that day, or the patient is seeing another doctor at the same time.
- Cancelling frees the slot. The appointment stays in the file with status `cancelled`.

## Files

```
app.py            Flask routes
scheduler.py      booking logic and data structures
validation.py     form checks
storage.py        CSV/JSON read and write (atomic writes)
errors.py         custom exceptions
analysis.py       pandas analysis
charts.py         matplotlib charts
seed_data.py      sample data
config.py         OPD hours, slot length, default doctors
templates/        HTML pages
static/style.css  styling
data/             created on first run
```

`app.py` uses Flask's development server, which is fine for a demo or class project. Set `CAREQUEUE_SECRET` to a fixed random string if you need flash messages to survive restarts.

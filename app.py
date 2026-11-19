"""CareQueue website. Run with:  python app.py   then open http://127.0.0.1:5000"""
import os
from datetime import date, datetime

from flask import Flask, Response, abort, flash, jsonify, redirect, render_template, request, url_for

import analysis
import charts
import config
from errors import CareQueueError
from scheduler import SLOTS, CareQueue
from validation import parse_date


def create_app(data_dir=None):
    app = Flask(__name__)
    # Set CAREQUEUE_SECRET in production so flash messages survive restarts.
    app.secret_key = os.environ.get("CAREQUEUE_SECRET") or os.urandom(24)
    cq = CareQueue(data_dir)
    app.config["CQ"] = cq

    @app.context_processor
    def globals_for_templates():
        return {"doctors": cq.doctors, "patients": cq.patients, "today": date.today().isoformat(), "cfg": config}

    @app.template_filter("weekday")
    def weekday_filter(date_str):
        return config.WEEKDAY_NAMES[parse_date(date_str).weekday()]

    @app.template_filter("pretty_date")
    def pretty_date(date_str):
        return parse_date(date_str).strftime("%a %d %b %Y")

    # ---------- dashboard ----------

    @app.get("/")
    def dashboard():
        today = date.today().isoformat()
        now_slot = datetime.now().strftime("%H:%M")
        todays = [a for a in cq.list_appointments(date_str=today, status="booked")]
        per_doctor = []
        for d in cq.doctors.values():
            working = cq.works_on(d["doctor_id"], date.today())
            booked = sum(1 for a in todays if a["doctor_id"] == d["doctor_id"])
            per_doctor.append({**d, "working": working, "booked": booked, "free": len(SLOTS) - booked if working else 0})
        upcoming = sorted((a for a in todays if a["slot"] >= now_slot), key=lambda a: (a["slot"], a["doctor_id"]))[:8]
        return render_template(
            "dashboard.html",
            todays_count=len(todays),
            per_doctor=per_doctor,
            upcoming=upcoming,
            patient_count=len(cq.patients),
            slots_per_day=len(SLOTS),
        )

    # ---------- patients ----------

    @app.route("/patients", methods=["GET", "POST"])
    def patients():
        form = {}
        if request.method == "POST":
            form = request.form
            try:
                p = cq.register_patient(form)
            except CareQueueError as e:
                flash(str(e), "error")
            else:
                flash(f"Registered {p['name']} as {p['patient_id']}.", "success")
                return redirect(url_for("patient_detail", patient_id=p["patient_id"]))
        q = request.args.get("q", "")
        return render_template("patients.html", rows=cq.find_patients(q)[:200], q=q, form=form)

    @app.get("/patients/<patient_id>")
    def patient_detail(patient_id):
        try:
            patient = cq.get_patient(patient_id)
        except CareQueueError as e:
            flash(str(e), "error")
            return redirect(url_for("patients"))
        history = cq.list_appointments(patient_id=patient["patient_id"])
        visits = sum(1 for a in history if a["status"] == "booked")
        return render_template("patient_detail.html", patient=patient, history=history, visits=visits)

    # ---------- appointments ----------

    @app.route("/book", methods=["GET", "POST"])
    def book():
        form = request.form if request.method == "POST" else request.args
        if request.method == "POST":
            try:
                appt = cq.book(form.get("patient_id"), form.get("doctor_id"), form.get("date"), form.get("slot"))
            except CareQueueError as e:
                flash(str(e), "error")
            else:
                flash(f"Booked. Token {appt['token']} at {appt['slot']}.", "success")
                return redirect(url_for("appointment_slip", appointment_id=appt["appointment_id"]))
        return render_template("book.html", form=form)

    @app.get("/appointments")
    def appointments():
        f = {k: request.args.get(k, "") for k in ("date", "doctor_id", "status", "patient_id")}
        try:
            if f["date"]:
                parse_date(f["date"])
        except CareQueueError as e:
            flash(str(e), "error")
            f["date"] = ""
        rows = cq.list_appointments(
            date_str=f["date"] or None,
            doctor_id=f["doctor_id"] or None,
            status=f["status"] or None,
            patient_id=f["patient_id"].strip().upper() or None,
        )
        return render_template("appointments.html", rows=rows[:300], total=len(rows), f=f)

    @app.get("/appointments/<appointment_id>")
    def appointment_slip(appointment_id):
        try:
            appt = cq.get_appointment(appointment_id)
        except CareQueueError:
            abort(404)
        return render_template("slip.html", a=appt, patient=cq.patients.get(appt["patient_id"]), doctor=cq.doctors[appt["doctor_id"]])

    @app.post("/appointments/<appointment_id>/cancel")
    def cancel(appointment_id):
        try:
            appt = cq.cancel(appointment_id)
        except CareQueueError as e:
            flash(str(e), "error")
        else:
            flash(f"Cancelled token {appt['token']} ({appt['slot']} on {appt['date']}). The slot is free again.", "success")
        next_url = request.form.get("next", "")
        # Only follow local paths, so the form can't be used to redirect off-site.
        if not next_url.startswith("/") or next_url.startswith("//"):
            next_url = url_for("appointments")
        return redirect(next_url)

    @app.get("/doctor-day")
    def doctor_day():
        doctor_id = request.args.get("doctor_id") or next(iter(cq.doctors))
        day = request.args.get("date") or date.today().isoformat()
        try:
            rows = cq.doctor_day(doctor_id, day)
            working = cq.works_on(doctor_id, parse_date(day))
        except CareQueueError as e:
            flash(str(e), "error")
            return redirect(url_for("doctor_day"))
        booked = sum(1 for r in rows if r["appointment"])
        return render_template(
            "doctor_day.html", rows=rows, doctor=cq.doctors[doctor_id], day=day, working=working, booked=booked
        )

    @app.get("/api/slots")
    def api_slots():
        doctor_id, day = request.args.get("doctor_id", ""), request.args.get("date", "")
        try:
            doctor = cq.get_doctor(doctor_id)
            d = parse_date(day)
            if not cq.works_on(doctor_id, d):
                days = ", ".join(config.WEEKDAY_NAMES[i][:3] for i in doctor["working_days"])
                return jsonify(slots=[], message=f"{doctor['name']} holds OPD on {days} only.")
            slots = cq.available_slots(doctor_id, day)
        except CareQueueError as e:
            return jsonify(slots=[], message=str(e)), 400
        message = f"{len(slots)} of {len(SLOTS)} slots free." if slots else "No slots left on this day."
        return jsonify(slots=slots, message=message)

    # ---------- analysis ----------

    @app.get("/analysis")
    def analysis_page():
        s = analysis.summary(cq)
        return render_template("analysis.html", s=s)

    chart_builders = {
        "department": lambda s: charts.department_load_chart(s["department_load"]),
        "daily": lambda s: charts.daily_chart(s["daily"]),
        "hourly": lambda s: charts.hourly_heat_chart(s["hours"]),
        "weekday": lambda s: charts.weekday_chart(s["weekdays"]),
    }

    @app.get("/charts/<name>.png")
    def chart(name):
        if name not in chart_builders:
            abort(404)
        png = chart_builders[name](analysis.summary(cq))
        return Response(png, mimetype="image/png", headers={"Cache-Control": "no-store"})

    return app


if __name__ == "__main__":
    create_app().run(debug=os.environ.get("FLASK_DEBUG") == "1", port=int(os.environ.get("PORT", 5000)))

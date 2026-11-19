"""pandas analysis of appointments: department load, busiest days and hours, repeat visitors.

Only booked (not cancelled) appointments count as visits.
"""
import pandas as pd

from config import WEEKDAY_NAMES


def appointments_frame(cq):
    """Booked appointments joined with patient and doctor details."""
    columns = ["appointment_id", "token", "patient_id", "doctor_id", "department", "date", "slot", "status"]
    df = pd.DataFrame(cq.appointments, columns=columns)
    df = df[df["status"] == "booked"].copy()
    if df.empty:
        return df

    patients = pd.DataFrame(list(cq.patients.values()), columns=["patient_id", "name", "age", "gender"])
    doctors = pd.DataFrame(list(cq.doctors.values()))[["doctor_id", "name"]].rename(columns={"name": "doctor"})
    df = df.merge(patients, on="patient_id", how="left").merge(doctors, on="doctor_id", how="left")

    df["date"] = pd.to_datetime(df["date"])
    df["weekday"] = pd.Categorical(df["date"].dt.day_name(), categories=WEEKDAY_NAMES, ordered=True)
    df["hour"] = df["slot"].str.slice(0, 2).astype(int)
    return df


def department_load(df):
    """Appointments and distinct patients per department, busiest first."""
    if df.empty:
        return pd.DataFrame(columns=["department", "appointments", "patients"])
    out = (
        df.groupby("department")
        .agg(appointments=("appointment_id", "count"), patients=("patient_id", "nunique"))
        .sort_values("appointments", ascending=False)
        .reset_index()
    )
    return out


def daily_counts(df):
    """Appointments per calendar date, with zero for dates in between that had none."""
    if df.empty:
        return pd.Series(dtype=int)
    counts = df.groupby("date").size()
    full_range = pd.date_range(counts.index.min(), counts.index.max(), freq="D")
    return counts.reindex(full_range, fill_value=0)


def weekday_counts(df):
    """Total and average appointments per weekday (Sunday dropped when OPD is closed)."""
    if df.empty:
        return pd.DataFrame(columns=["weekday", "appointments", "average_per_day"])
    total = df.groupby("weekday", observed=False).size()
    days_seen = df.drop_duplicates("date").groupby("weekday", observed=False).size()
    out = pd.DataFrame({"appointments": total, "days": days_seen})
    out = out[out["days"] > 0]
    out["average_per_day"] = (out["appointments"] / out["days"]).round(1)
    return out.drop(columns="days").reset_index()


def hourly_counts(df):
    """Appointments per hour of the day."""
    if df.empty:
        return pd.Series(dtype=int)
    counts = df.groupby("hour").size()
    return counts.reindex(sorted(counts.index), fill_value=0)


def repeat_patients(df, min_visits=2):
    """Patients with at least min_visits booked appointments."""
    if df.empty:
        return pd.DataFrame(columns=["patient_id", "name", "visits", "departments", "first_visit", "last_visit"])
    out = (
        df.groupby(["patient_id", "name"])
        .agg(
            visits=("appointment_id", "count"),
            departments=("department", lambda s: ", ".join(sorted(s.unique()))),
            first_visit=("date", "min"),
            last_visit=("date", "max"),
        )
        .reset_index()
    )
    out = out[out["visits"] >= min_visits].sort_values(["visits", "last_visit"], ascending=False)
    out["first_visit"] = out["first_visit"].dt.strftime("%Y-%m-%d")
    out["last_visit"] = out["last_visit"].dt.strftime("%Y-%m-%d")
    return out


def busiest_dates(df, n=5):
    if df.empty:
        return pd.DataFrame(columns=["date", "weekday", "appointments"])
    out = df.groupby(["date", "weekday"], observed=True).size().reset_index(name="appointments")
    out = out.sort_values(["appointments", "date"], ascending=[False, False]).head(n)
    out["date"] = out["date"].dt.strftime("%Y-%m-%d")
    return out


def summary(cq):
    """Everything the analysis page needs, in one dict."""
    df = appointments_frame(cq)
    total_all = len(cq.appointments)
    cancelled = sum(1 for a in cq.appointments if a["status"] == "cancelled")
    hours = hourly_counts(df)
    weekdays = weekday_counts(df)
    repeats = repeat_patients(df)
    return {
        "df": df,
        "total_booked": len(df),
        "total_cancelled": cancelled,
        "cancel_rate": round(100 * cancelled / total_all, 1) if total_all else 0.0,
        "unique_patients": int(df["patient_id"].nunique()) if not df.empty else 0,
        "repeat_count": len(repeats),
        "department_load": department_load(df),
        "daily": daily_counts(df),
        "weekdays": weekdays,
        "busiest_weekday": weekdays.sort_values("average_per_day", ascending=False).iloc[0]["weekday"] if not weekdays.empty else None,
        "hours": hours,
        "busiest_hour": int(hours.idxmax()) if not hours.empty else None,
        "busiest_dates": busiest_dates(df),
        "repeat_patients": repeats,
    }

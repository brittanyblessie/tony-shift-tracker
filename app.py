"""
Title: Tony's Shift Tracker
Author: Brittany Blessie
Date: 2026-03-14
Modified By: Claude
Description: A Streamlit app for Tony to log shifts and tips, with a dashboard
             for Brittany showing totals, tax set-aside, and retirement savings.
             Data is stored in Google Sheets.
"""

import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, date, time
import pandas as pd
import json
import os

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Tony's Shift Tracker",
    page_icon="💰",
    layout="centered"
)

# ── Constants ─────────────────────────────────────────────────────────────────
PASSWORD        = "8372"
HOURLY_RATE     = 16.90
TAX_RATE        = 0.3865          # federal 22% + CA state 9.3% + FICA 7.65%
RETIREMENT_PCT  = 0.10
SHEET_URL       = "https://docs.google.com/spreadsheets/d/146EL7E7DLj-RADnlTj4cz2tTNbwjV_IS_2ssv2ffs5I/edit"
CREDS_FILE      = "tony-shift-tracker.json"
SHEET_HEADERS   = ["Timestamp", "Date", "Shift Type", "Clock In", "Clock Out",
                   "Hours Worked", "All Sales", "Tip Out", "Tips Earned",
                   "Wages", "Total Earned", "Tax Set Aside", "Retirement Set Aside",
                   "Busy Rating", "Covers", "Holiday Shift", "Double Shift", "Notes"]

# ── Google Sheets connection ──────────────────────────────────────────────────
@st.cache_resource
def get_sheet():
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]
    # Use Streamlit secrets when deployed, fall back to local JSON file
    try:
        if "gcp_service_account" in st.secrets:
            creds = Credentials.from_service_account_info(
                st.secrets["gcp_service_account"],
                scopes=scope
            )
        else:
            creds = Credentials.from_service_account_file(CREDS_FILE, scopes=scope)
    except Exception as e:
        st.error(f"Credentials error: {e}")
        st.stop()
    client = gspread.authorize(creds)
    sh = client.open_by_url(SHEET_URL)
    worksheet = sh.sheet1
    if worksheet.row_count == 0 or worksheet.cell(1, 1).value != "Timestamp":
        worksheet.clear()
        worksheet.append_row(SHEET_HEADERS)
    return worksheet

def load_data():
    try:
        ws = get_sheet()
        data = ws.get_all_records()
        if not data:
            return pd.DataFrame(columns=SHEET_HEADERS)
        df = pd.DataFrame(data)
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
        for col in ["All Sales", "Tip Out", "Tips Earned", "Wages",
                    "Total Earned", "Tax Set Aside", "Retirement Set Aside",
                    "Hours Worked", "Covers"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
        return df
    except Exception as e:
        st.error(f"Could not load data: {e}")
        return pd.DataFrame(columns=SHEET_HEADERS)

def calc_hours(clock_in_t, clock_out_t):
    try:
        in_mins  = clock_in_t.hour  * 60 + clock_in_t.minute
        out_mins = clock_out_t.hour * 60 + clock_out_t.minute
        diff = out_mins - in_mins
        if diff < 0:
            diff += 24 * 60
        return round(diff / 60, 2)
    except:
        return 0.0

def parse_time_12h(s):
    if not s:
        return None
    import re
    s = s.strip().upper().replace(" ", "").replace(":", "")
    # Extract AM/PM
    ampm = None
    if s.endswith("AM"):
        ampm = "AM"; s = s[:-2]
    elif s.endswith("PM"):
        ampm = "PM"; s = s[:-2]
    elif s.endswith("A"):
        ampm = "AM"; s = s[:-1]
    elif s.endswith("P"):
        ampm = "PM"; s = s[:-1]
    if not s.isdigit():
        return None
    # Parse digits into hour/minute
    if len(s) <= 2:
        hour = int(s); minute = 0
    elif len(s) == 3:
        hour = int(s[0]); minute = int(s[1:])
    elif len(s) == 4:
        hour = int(s[:2]); minute = int(s[2:])
    else:
        return None
    if not ampm:
        # 10:30-11:59 = AM, everything else (12-10:29) = PM
        if hour == 10 and minute >= 30:
            ampm = "AM"
        elif hour == 11:
            ampm = "AM"
        else:
            ampm = "PM"
    if hour == 12:
        hour = 0 if ampm == "AM" else 12
    elif ampm == "PM":
        hour += 12
    try:
        return time(hour % 24, minute)
    except:
        return None

def fmt_12h(t):
    """Format a time object as 12-hour string for display."""
    return t.strftime("%I:%M %p").lstrip("0")

# ── Session state ─────────────────────────────────────────────────────────────
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "submitted" not in st.session_state:
    st.session_state.submitted = False
if "last_entry" not in st.session_state:
    st.session_state.last_entry = {}
if "clock_in_val" not in st.session_state:
    st.session_state.clock_in_val = ""
if "clock_out_val" not in st.session_state:
    st.session_state.clock_out_val = ""
if "active_tab" not in st.session_state:
    st.session_state.active_tab = "log"""

# ── Password screen ───────────────────────────────────────────────────────────
if not st.session_state.authenticated:
    st.markdown("## 💰 Tony's Shift Tracker")
    st.markdown("Enter your PIN to continue.")
    pin = st.text_input("PIN", type="password", max_chars=4, placeholder="Enter 4-digit PIN")
    if st.button("Unlock", use_container_width=True):
        if pin == PASSWORD:
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("Incorrect PIN. Try again.")
    st.stop()

# ── Main app ──────────────────────────────────────────────────────────────────
# Set default tab based on session state
_tab_index = {"log": 0, "dashboard": 1, "history": 2}.get(st.session_state.get("active_tab","log"), 0)
tab1, tab2, tab3 = st.tabs(["📋 Log a Shift", "📊 Dashboard", "📅 Shift History"])

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 1 — TONY'S FORM
# ═══════════════════════════════════════════════════════════════════════════════
with tab1:
    st.markdown("### Hey Tony! How was your shift? 👋")

    # ── Success summary ───────────────────────────────────────────────────────
    if st.session_state.submitted and st.session_state.last_entry:
        e = st.session_state.last_entry
        st.success("Shift logged! Great work! 🎉")
        st.markdown("---")

        st.markdown("#### This shift")
        c1, c2, c3 = st.columns(3)
        c1.metric("Tips earned",  f"${e['tips']:.2f}")
        c2.metric("Wages",        f"${e['wages']:.2f}")
        c3.metric("Total earned", f"${e['total']:.2f}")

        if e.get("all_sales", 0) > 0:
            c4, c5 = st.columns(2)
            c4.metric("All sales",  f"${e['all_sales']:.2f}")
            c5.metric("Tip out",    f"${e['tip_out']:.2f}")

        st.markdown("#### Set aside from this shift")
        c6, c7 = st.columns(2)
        c6.metric("For taxes 🏦",      f"${e['tax']:.2f}")
        c7.metric("For retirement 📈", f"${e['retirement']:.2f}")

        if e.get("tax_gap", 0) > 0:
            st.warning(f"⚠️ Heads up — consider setting aside an extra **${e['tax_gap']:.2f}** from tips to cover taxes this shift.")

        st.markdown("---")
        st.markdown("#### Your running totals")
        df = load_data()
        now      = datetime.now()
        month_df = df[df["Date"].dt.month == now.month] if not df.empty else df
        year_df  = df[df["Date"].dt.year  == now.year]  if not df.empty else df

        c8, c9 = st.columns(2)
        c8.metric("Tips this month", f"${month_df['Tips Earned'].sum():.2f}")
        c9.metric("Tips this year",  f"${year_df['Tips Earned'].sum():.2f}")

        c10, c11 = st.columns(2)
        c10.metric("Total earned this month", f"${month_df['Total Earned'].sum():.2f}")
        c11.metric("Total earned this year",  f"${year_df['Total Earned'].sum():.2f}")

        c12, c13 = st.columns(2)
        c12.metric("Tax set aside this month",        f"${month_df['Tax Set Aside'].sum():.2f}")
        c13.metric("Retirement set aside this month", f"${month_df['Retirement Set Aside'].sum():.2f}")

        st.markdown("---")
        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            if st.button("📋 Log another shift", use_container_width=True):
                st.session_state.submitted  = False
                st.session_state.last_entry = {}
                st.rerun()
        with col_btn2:
            if st.button("📊 Go to Dashboard", use_container_width=True):
                st.session_state.submitted  = False
                st.session_state.last_entry = {}
                st.session_state.active_tab = "dashboard"
                st.rerun()
        st.stop()

    # ── Form (no st.form wrapper — prevents enter-to-submit) ─────────────────
    with st.container():

        # Date — shown as MM/DD/YYYY
        shift_date = st.date_input(
            "Date",
            value=date.today(),
            format="MM/DD/YYYY",
            key="f_date"
        )

        # Shift type — default Day shift
        st.markdown("**Shift type**")
        shift_type = st.radio(
            "Shift type",
            ["☀️ Day shift", "🌙 Night shift"],
            index=0,
            horizontal=True,
            label_visibility="collapsed",
            key="f_shift"
        )

        # Clock in / out — smart text input, no military time
        st.markdown("**Clock in / Clock out**")
        st.caption("Just type it simply — like **11am**, **4pm**, **330pm**, or **1145am**")
        col1, col2 = st.columns(2)
        with col1:
            clock_in_raw  = st.text_input("Clock in",  placeholder="e.g. 11am", key="f_clock_in")
        with col2:
            clock_out_raw = st.text_input("Clock out", placeholder="e.g. 4pm",  key="f_clock_out")

        clock_in  = parse_time_12h(clock_in_raw)
        clock_out = parse_time_12h(clock_out_raw)
        if clock_in and clock_out:
            hours_preview = calc_hours(clock_in, clock_out)
            def to_12h(t):
                return t.strftime("%I:%M %p").lstrip("0")
            st.caption(f"⏰ {to_12h(clock_in)} → {to_12h(clock_out)}  ·  {hours_preview:.2f} hrs worked")
        elif clock_in_raw or clock_out_raw:
            st.caption("Hmm, couldn't read that time. Try something like 11am or 330pm")

        # Sales section
        st.markdown("**Sales**")
        col3, col4 = st.columns(2)
        with col3:
            all_sales = st.number_input(
                "All sales ($)",
                min_value=0.0, step=0.01, format="%.2f",
                help="Total sales for your section today",
                key="f_sales"
            )
        with col4:
            tip_out = st.number_input(
                "Tip out ($)",
                min_value=0.0, step=0.01, format="%.2f",
                help="Amount tipped out to support staff",
                key="f_tipout"
            )

        tips = st.number_input(
            "Tips earned ($)",
            min_value=0.0, step=0.01, format="%.2f",
            help="Your actual tips after tip out",
            key="f_tips"
        )

        # Busy rating — no default, Tony must choose
        st.markdown("**How busy was it?**")
        busy = st.radio(
            "Busy rating",
            ["😴 Slow", "🙂 Normal", "😤 Busy", "🔥 Slammed"],
            index=None,
            horizontal=True,
            label_visibility="collapsed",
            key="f_busy"
        )

        # Covers
        covers = st.number_input(
            "How many covers did the restaurant have?",
            min_value=0, step=1, value=0,
            key="f_covers"
        )

        # Special shift flags
        st.markdown("**Special shift?**")
        is_holiday = st.checkbox("🎉 Holiday shift", value=False, key="f_holiday")
        is_double  = st.checkbox("⚡ This shift is part of a double shift", value=False, key="f_double")

        notes = st.text_input(
            "Notes (optional)",
            placeholder="e.g. special event, training, private party...",
            key="f_notes"
        )

        submitted = st.button("Log my shift! 💪", use_container_width=True, key="f_submit")

    if submitted:
        # Validate required fields
        errors = []
        if clock_in is None:
            errors.append("Clock in time is not valid. Try something like 11:30 AM.")
        if clock_out is None:
            errors.append("Clock out time is not valid. Try something like 4:00 PM.")
        if tips is None or tips <= 0:
            errors.append("Tips earned is required. Enter the amount you made in tips.")
        if busy is None:
            errors.append("Please select how busy it was.")
        if errors:
            for e in errors:
                st.error(e)
        else:
            hours         = calc_hours(clock_in, clock_out)
            wages         = round(hours * HOURLY_RATE, 2)
            total         = round(tips + wages, 2)
            tax_set_aside = round(tips * TAX_RATE, 2)
            retirement    = round(total * RETIREMENT_PCT, 2)
            expected_wage_tax = round(wages * TAX_RATE, 2)
            tax_gap       = max(0, round(expected_wage_tax - wages, 2))

            def to_12h(t):
                return t.strftime("%I:%M %p").lstrip("0")
            clock_in_str  = to_12h(clock_in)
            clock_out_str = to_12h(clock_out)

            row = [
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                shift_date.strftime("%m/%d/%Y"),
                shift_type.split(" ", 1)[1],
                clock_in_str,
                clock_out_str,
                hours,
                all_sales,
                tip_out,
                tips,
                wages,
                total,
                tax_set_aside,
                retirement,
                busy.split(" ", 1)[1],
                covers,
                "Yes" if is_holiday else "No",
                "Yes" if is_double  else "No",
                notes
            ]

            try:
                ws = get_sheet()
                ws.append_row(row)
                st.session_state.submitted  = True
                st.session_state.last_entry = {
                    "tips": tips, "wages": wages, "total": total,
                    "tax": tax_set_aside, "retirement": retirement,
                    "tax_gap": tax_gap, "all_sales": all_sales,
                    "tip_out": tip_out
                }
                st.cache_resource.clear()
                for key in ["f_date","f_shift","f_clock_in","f_clock_out",
                            "f_sales","f_tipout","f_tips","f_busy",
                            "f_covers","f_holiday","f_double","f_notes"]:
                    if key in st.session_state:
                        del st.session_state[key]
                st.rerun()
            except Exception as ex:
                st.error(f"Could not save shift: {ex}")

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 2 — DASHBOARD
# ═══════════════════════════════════════════════════════════════════════════════
with tab2:
    df = load_data()

    if df.empty or len(df) == 0:
        st.info("No shifts logged yet. Have Tony log his first shift!")
        st.stop()

    now      = datetime.now()
    month_df = df[df["Date"].dt.month == now.month]
    year_df  = df[df["Date"].dt.year  == now.year]

    month_tips  = month_df["Tips Earned"].sum()
    month_total = month_df["Total Earned"].sum()
    month_tax   = month_df["Tax Set Aside"].sum()
    month_ret   = month_df["Retirement Set Aside"].sum()
    month_shifts= len(month_df)
    year_tips   = year_df["Tips Earned"].sum()
    year_total  = year_df["Total Earned"].sum()

    # ── Goals (editable in sidebar) ───────────────────────────────────────────
    with st.sidebar:
        st.markdown("### 🎯 Monthly goals")
        tip_goal   = st.number_input("Tip goal ($)",           min_value=0, value=3000, step=100)
        total_goal = st.number_input("Total earnings goal ($)", min_value=0, value=5000, step=100)

    # ── Motivational message ──────────────────────────────────────────────────
    tip_pct = (month_tips / tip_goal * 100) if tip_goal > 0 else 0
    if tip_pct >= 100:
        msg = "🏆 GOAL CRUSHED! Tony you absolute legend! Take a bow!"
    elif tip_pct >= 75:
        msg = "🔥 So close!! You're on fire — keep it up Tony!"
    elif tip_pct >= 50:
        msg = "💪 Halfway there! You're doing amazing, keep grinding!"
    elif tip_pct >= 25:
        msg = "🚀 Great start! Every shift gets you closer — let's go!"
    else:
        msg = "✨ The month is young! Time to show them what you've got Tony!"

    st.markdown(f"##### {msg}")
    st.markdown("---")

    # ── Big colorful metric cards ─────────────────────────────────────────────
    st.markdown("### 💰 This month")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("💵 Total earned",   f"${month_total:,.2f}")
    c2.metric("🤑 Tips earned",    f"${month_tips:,.2f}")
    c3.metric("🏦 Tax set aside",  f"${month_tax:,.2f}")
    c4.metric("📈 Retirement",     f"${month_ret:,.2f}")

    col_a, col_b = st.columns(2)
    col_a.metric("📅 Shifts this month", month_shifts)
    col_b.metric("⭐ Avg tips per shift", f"${(month_tips/month_shifts):,.2f}" if month_shifts > 0 else "$0.00")

    st.markdown("---")

    # ── Progress bars ─────────────────────────────────────────────────────────
    st.markdown("### 🎯 Monthly goals")

    tip_pct_capped   = min(tip_pct, 100)
    total_pct        = min((month_total / total_goal * 100) if total_goal > 0 else 0, 100)

    st.markdown(f"**💵 Tip goal** — ${month_tips:,.2f} of ${tip_goal:,.2f}")
    st.progress(int(tip_pct_capped))
    remaining_tips = max(0, tip_goal - month_tips)
    if remaining_tips > 0:
        st.caption(f"${remaining_tips:,.2f} to go — you've got this! 💪")
    else:
        st.caption("✅ Goal reached!")

    st.markdown(f"**🏆 Total earnings goal** — ${month_total:,.2f} of ${total_goal:,.2f}")
    st.progress(int(total_pct))
    remaining_total = max(0, total_goal - month_total)
    if remaining_total > 0:
        st.caption(f"${remaining_total:,.2f} to go!")
    else:
        st.caption("✅ Goal reached!")

    st.markdown("---")

    # ── Charts ────────────────────────────────────────────────────────────────
    st.markdown("### 📊 Charts")

    # Monthly tips bar chart
    if not year_df.empty:
        st.markdown("**Tips by month**")
        monthly = (
            year_df.groupby(year_df["Date"].dt.month)["Tips Earned"]
            .sum().reset_index()
        )
        monthly.columns = ["Month", "Tips"]
        monthly["Month"] = monthly["Month"].apply(
            lambda m: datetime(now.year, m, 1).strftime("%b")
        )
        st.bar_chart(monthly.set_index("Month"))

    # Avg tips by shift type
    if not df.empty and df["Shift Type"].nunique() > 1:
        st.markdown("**Average tips by shift type**")
        shift_avg = df.groupby("Shift Type")["Tips Earned"].mean().reset_index()
        shift_avg.columns = ["Shift Type", "Avg Tips"]
        shift_avg["Avg Tips"] = shift_avg["Avg Tips"].round(2)
        st.bar_chart(shift_avg.set_index("Shift Type"))

    # Busy rating breakdown
    if not df.empty and "Busy Rating" in df.columns:
        st.markdown("**Shifts by busy rating**")
        busy_counts = df["Busy Rating"].value_counts().reset_index()
        busy_counts.columns = ["Rating", "Shifts"]
        st.bar_chart(busy_counts.set_index("Rating"))

    st.markdown("---")

    # ── Year totals ───────────────────────────────────────────────────────────
    st.markdown("### 📅 This year")
    c5, c6, c7, c8 = st.columns(4)
    c5.metric("💵 Total earned",  f"${year_total:,.2f}")
    c6.metric("🤑 Tips earned",   f"${year_tips:,.2f}")
    c7.metric("🏦 Tax set aside", f"${year_df['Tax Set Aside'].sum():,.2f}")
    c8.metric("📈 Retirement",    f"${year_df['Retirement Set Aside'].sum():,.2f}")

    st.markdown("---")

    # ── Sales summary ─────────────────────────────────────────────────────────
    if "All Sales" in df.columns and month_df["All Sales"].sum() > 0:
        st.markdown("### 🧾 Sales this month")
        c9, c10, c11 = st.columns(3)
        c9.metric("All sales",            f"${month_df['All Sales'].sum():,.2f}")
        c10.metric("Tip out",             f"${month_df['Tip Out'].sum():,.2f}")
        c11.metric("Avg covers per shift",f"{month_df['Covers'].mean():.0f}")
        st.markdown("---")

    # ── Full shift log ────────────────────────────────────────────────────────
    st.markdown("### 🗂️ All shifts")
    display_df = df.copy()
    display_df["Date"] = display_df["Date"].dt.strftime("%m/%d/%Y")
    for col in ["All Sales", "Tip Out", "Tips Earned", "Wages",
                "Total Earned", "Tax Set Aside", "Retirement Set Aside"]:
        if col in display_df.columns:
            display_df[col] = display_df[col].apply(lambda x: f"${x:,.2f}")
    show_cols = ["Date", "Shift Type", "Clock In", "Clock Out", "Hours Worked",
                 "All Sales", "Tip Out", "Tips Earned", "Wages", "Total Earned",
                 "Tax Set Aside", "Retirement Set Aside", "Busy Rating", "Covers", "Notes"]
    show_cols = [c for c in show_cols if c in display_df.columns]
    st.dataframe(display_df[show_cols], use_container_width=True, hide_index=True)

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 3 — SHIFT HISTORY & EDITING
# ═══════════════════════════════════════════════════════════════════════════════
with tab3:
    st.markdown("### Shift history 📅")

    df = load_data()

    if df.empty or len(df) == 0:
        st.info("No shifts logged yet. Have Tony log his first shift!")
        st.stop()

    # Sort most recent first and add a row number for Google Sheets reference
    df_sorted = df.copy()
    df_sorted = df_sorted.sort_values("Date", ascending=False).reset_index(drop=True)
    # Row in Google Sheet = index in sorted df + 2 (1 for header, 1 for 1-based)
    # We need original order to find the right sheet row so track original index
    df_sorted["_sheet_row"] = df_sorted.index  # placeholder, recalculated below

    # Load raw sheet rows to map to actual sheet positions
    try:
        ws = get_sheet()
        all_rows = ws.get_all_values()  # includes header
        # Build a lookup: timestamp -> sheet row number (1-based, row 1 = header)
        ts_to_row = {}
        for i, row in enumerate(all_rows[1:], start=2):  # skip header
            if row:
                ts_to_row[row[0]] = i  # row[0] = Timestamp
    except Exception as ex:
        st.error(f"Could not load sheet rows: {ex}")
        st.stop()

    # ── Shift list ────────────────────────────────────────────────────────────
    if "editing_row" not in st.session_state:
        st.session_state.editing_row = None

    for idx, row in df_sorted.iterrows():
        date_str  = row["Date"].strftime("%m/%d/%Y") if pd.notna(row["Date"]) else "Unknown date"
        shift     = row.get("Shift Type", "")
        tips      = row.get("Tips Earned", 0)
        total     = row.get("Total Earned", 0)
        busy      = row.get("Busy Rating", "")
        ts        = row.get("Timestamp", "")
        sheet_row = ts_to_row.get(str(ts), None)

        with st.expander(f"📅 {date_str}  ·  {shift}  ·  Tips: ${tips:.2f}  ·  Total: ${total:.2f}"):
            c1, c2, c3, c4 = st.columns(4)
            c1.markdown(f"**Clock in**\n\n{row.get('Clock In','—')}")
            c2.markdown(f"**Clock out**\n\n{row.get('Clock Out','—')}")
            c3.markdown(f"**Hours**\n\n{row.get('Hours Worked', 0):.2f} hrs")
            c4.markdown(f"**Busy**\n\n{busy}")

            c5, c6, c7 = st.columns(3)
            c5.markdown(f"**All sales**\n\n${row.get('All Sales', 0):.2f}")
            c6.markdown(f"**Tip out**\n\n${row.get('Tip Out', 0):.2f}")
            c7.markdown(f"**Covers**\n\n{int(row.get('Covers', 0))}")

            c8, c9, c10 = st.columns(3)
            c8.markdown(f"**Wages**\n\n${row.get('Wages', 0):.2f}")
            c9.markdown(f"**Tax set aside**\n\n${row.get('Tax Set Aside', 0):.2f}")
            c10.markdown(f"**Retirement**\n\n${row.get('Retirement Set Aside', 0):.2f}")

            if row.get("Notes"):
                st.markdown(f"**Notes:** {row.get('Notes')}")

            if sheet_row:
                if st.button(f"✏️ Edit this shift", key=f"edit_{idx}"):
                    st.session_state.editing_row = {"idx": idx, "sheet_row": sheet_row, "data": row}
                    st.rerun()

    # ── Edit form ─────────────────────────────────────────────────────────────
    if st.session_state.editing_row:
        er   = st.session_state.editing_row
        erow = er["data"]
        sr   = er["sheet_row"]

        st.markdown("---")
        st.markdown("### ✏️ Editing shift")

        with st.form("edit_form"):
            edit_date = st.date_input(
                "Date",
                value=erow["Date"].date() if pd.notna(erow["Date"]) else date.today(),
                format="MM/DD/YYYY"
            )

            st.markdown("**Shift type**")
            shift_options = ["Day shift", "Night shift"]
            current_shift = erow.get("Shift Type", "Day shift")
            edit_shift = st.radio(
                "Shift type",
                ["☀️ Day shift", "🌙 Night shift"],
                index=0 if "Day" in current_shift else 1,
                horizontal=True,
                label_visibility="collapsed"
            )

            # Parse existing times
            def parse_time_str(s):
                for fmt in ["%I:%M %p", "%H:%M", "%I:%M%p"]:
                    try:
                        return datetime.strptime(str(s).strip(), fmt).time()
                    except:
                        continue
                return time(11, 30)

            col1, col2 = st.columns(2)
            with col1:
                edit_in  = st.time_input("Clock in",  value=parse_time_str(erow.get("Clock In", "11:30 AM")))
            with col2:
                edit_out = st.time_input("Clock out", value=parse_time_str(erow.get("Clock Out", "4:00 PM")))

            hours_preview = calc_hours(edit_in, edit_out)
            st.caption(f"Hours worked: {hours_preview:.2f} hrs")

            st.markdown("**Sales**")
            col3, col4 = st.columns(2)
            with col3:
                edit_sales = st.number_input("All sales ($)", value=float(erow.get("All Sales", 0)), min_value=0.0, step=0.01, format="%.2f")
            with col4:
                edit_tipout = st.number_input("Tip out ($)", value=float(erow.get("Tip Out", 0)), min_value=0.0, step=0.01, format="%.2f")

            edit_tips = st.number_input("Tips earned ($)", value=float(erow.get("Tips Earned", 0)), min_value=0.0, step=0.01, format="%.2f")

            st.markdown("**How busy was it?**")
            busy_options = ["😴 Slow", "🙂 Normal", "😤 Busy", "🔥 Slammed"]
            busy_labels  = ["Slow", "Normal", "Busy", "Slammed"]
            current_busy = erow.get("Busy Rating", "Normal")
            busy_idx     = busy_labels.index(current_busy) if current_busy in busy_labels else 1
            edit_busy = st.radio(
                "Busy rating",
                busy_options,
                index=busy_idx,
                horizontal=True,
                label_visibility="collapsed"
            )

            edit_covers = st.number_input("Covers", value=int(erow.get("Covers", 0)), min_value=0, step=1)
            edit_notes  = st.text_input("Notes (optional)", value=erow.get("Notes", ""))

            col_save, col_cancel = st.columns(2)
            with col_save:
                save = st.form_submit_button("💾 Save changes", use_container_width=True)
            with col_cancel:
                cancel = st.form_submit_button("Cancel", use_container_width=True)

        if cancel:
            st.session_state.editing_row = None
            st.rerun()

        if save:
            hours      = calc_hours(edit_in, edit_out)
            wages      = round(hours * HOURLY_RATE, 2)
            total      = round(edit_tips + wages, 2)
            tax        = round(edit_tips * TAX_RATE, 2)
            retirement = round(total * RETIREMENT_PCT, 2)

            updated_row = [
                str(erow.get("Timestamp", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))),
                edit_date.strftime("%m/%d/%Y"),
                edit_shift.split(" ", 1)[1],
                fmt_12h(edit_in),
                fmt_12h(edit_out),
                hours,
                edit_sales,
                edit_tipout,
                edit_tips,
                wages,
                total,
                tax,
                retirement,
                edit_busy.split(" ", 1)[1],
                edit_covers,
                edit_notes
            ]

            try:
                ws = get_sheet()
                ws.update(f"A{sr}:P{sr}", [updated_row])
                st.session_state.editing_row = None
                st.cache_resource.clear()
                st.success("Shift updated!")
                st.rerun()
            except Exception as ex:
                st.error(f"Could not update shift: {ex}")
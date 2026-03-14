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
    creds = Credentials.from_service_account_file(CREDS_FILE, scopes=scope)
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
        if st.button("Log another shift", use_container_width=True):
            st.session_state.submitted  = False
            st.session_state.last_entry = {}
            st.rerun()
        st.stop()

    # ── Form ──────────────────────────────────────────────────────────────────
    with st.form("shift_form", clear_on_submit=True):

        # Date — shown as MM/DD/YYYY
        shift_date = st.date_input(
            "Date",
            value=date.today(),
            format="MM/DD/YYYY"
        )

        # Shift type — default Day shift
        st.markdown("**Shift type**")
        shift_type = st.radio(
            "Shift type",
            ["☀️ Day shift", "🌙 Night shift"],
            index=0,
            horizontal=True,
            label_visibility="collapsed"
        )

        # Clock in / out — typeable 12-hour text fields
        st.markdown("**Clock in / Clock out** (type time, e.g. 11:30 AM or 4:00 PM)")
        col1, col2 = st.columns(2)
        with col1:
            clock_in_raw  = st.text_input("Clock in",  value="11:30 AM", placeholder="e.g. 11:30 AM")
        with col2:
            clock_out_raw = st.text_input("Clock out", value="4:00 PM",  placeholder="e.g. 4:00 PM")

        # Parse and preview hours
        def parse_time_12h(s):
            for fmt in ["%I:%M %p", "%I:%M%p", "%H:%M", "%I %p", "%I%p"]:
                try:
                    return datetime.strptime(s.strip().upper(), fmt).time()
                except:
                    continue
            return None

        clock_in  = parse_time_12h(clock_in_raw)
        clock_out = parse_time_12h(clock_out_raw)
        if clock_in and clock_out:
            hours_preview = calc_hours(clock_in, clock_out)
            st.caption(f"Hours worked: {hours_preview:.2f} hrs")
        else:
            st.caption("Enter times like 11:30 AM and 4:00 PM")

        # Sales section
        st.markdown("**Sales**")
        col3, col4 = st.columns(2)
        with col3:
            all_sales = st.number_input(
                "All sales ($)",
                min_value=0.0, step=0.01, format="%.2f",
                help="Total sales for your section today"
            )
        with col4:
            tip_out = st.number_input(
                "Tip out ($)",
                min_value=0.0, step=0.01, format="%.2f",
                help="Amount tipped out to support staff"
            )

        tips = st.number_input(
            "Tips earned ($)",
            min_value=0.0, step=0.01, format="%.2f",
            help="Your actual tips after tip out"
        )

        # Busy rating — no default, Tony must choose
        st.markdown("**How busy was it?**")
        busy = st.radio(
            "Busy rating",
            ["😴 Slow", "🙂 Normal", "😤 Busy", "🔥 Slammed"],
            index=None,
            horizontal=True,
            label_visibility="collapsed"
        )

        # Covers
        covers = st.number_input(
            "How many covers did the restaurant have?",
            min_value=0, step=1, value=0
        )

        # Special shift flags
        st.markdown("**Special shift?**")
        is_holiday = st.checkbox("🎉 Holiday shift", value=False)
        is_double  = st.checkbox("⚡ This shift is part of a double shift", value=False)

        notes = st.text_input(
            "Notes (optional)",
            placeholder="e.g. special event, training, private party..."
        )

        submitted = st.form_submit_button("Log my shift! 💪", use_container_width=True)

    if submitted:
        # Validate required fields
        errors = []
        if clock_in is None:
            errors.append("Clock in time is not valid. Try something like 11:30 AM.")
        if clock_out is None:
            errors.append("Clock out time is not valid. Try something like 4:00 PM.")
        if tips <= 0:
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

            clock_in_str  = clock_in_raw.strip()
            clock_out_str = clock_out_raw.strip()

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
                st.rerun()
            except Exception as ex:
                st.error(f"Could not save shift: {ex}")

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 2 — BRITTANY'S DASHBOARD
# ═══════════════════════════════════════════════════════════════════════════════
with tab2:
    st.markdown("### Dashboard 📊")
    df = load_data()

    if df.empty or len(df) == 0:
        st.info("No shifts logged yet. Have Tony log his first shift!")
        st.stop()

    now      = datetime.now()
    month_df = df[df["Date"].dt.month == now.month]
    year_df  = df[df["Date"].dt.year  == now.year]

    # ── Summary metrics ───────────────────────────────────────────────────────
    st.markdown("#### This month")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total earned",   f"${month_df['Total Earned'].sum():,.2f}")
    c2.metric("Tips earned",    f"${month_df['Tips Earned'].sum():,.2f}")
    c3.metric("Tax set aside",  f"${month_df['Tax Set Aside'].sum():,.2f}")
    c4.metric("Retirement",     f"${month_df['Retirement Set Aside'].sum():,.2f}")

    st.markdown("#### This year")
    c5, c6, c7, c8 = st.columns(4)
    c5.metric("Total earned",   f"${year_df['Total Earned'].sum():,.2f}")
    c6.metric("Tips earned",    f"${year_df['Tips Earned'].sum():,.2f}")
    c7.metric("Tax set aside",  f"${year_df['Tax Set Aside'].sum():,.2f}")
    c8.metric("Retirement",     f"${year_df['Retirement Set Aside'].sum():,.2f}")

    st.markdown("---")

    # ── Sales metrics ─────────────────────────────────────────────────────────
    if "All Sales" in df.columns and df["All Sales"].sum() > 0:
        st.markdown("#### Sales summary (this month)")
        c9, c10, c11 = st.columns(3)
        c9.metric("All sales",   f"${month_df['All Sales'].sum():,.2f}")
        c10.metric("Tip out",    f"${month_df['Tip Out'].sum():,.2f}")
        c11.metric("Avg covers per shift", f"{month_df['Covers'].mean():.0f}")
        st.markdown("---")

    # ── Monthly tips chart ────────────────────────────────────────────────────
    st.markdown("#### Monthly tips")
    if not year_df.empty:
        monthly = (
            year_df.groupby(year_df["Date"].dt.month)["Tips Earned"]
            .sum()
            .reset_index()
        )
        monthly.columns = ["Month", "Tips"]
        monthly["Month"] = monthly["Month"].apply(
            lambda m: datetime(now.year, m, 1).strftime("%b")
        )
        st.bar_chart(monthly.set_index("Month"))

    # ── Avg tips by shift type ────────────────────────────────────────────────
    st.markdown("#### Average tips by shift type")
    if not df.empty:
        shift_avg = df.groupby("Shift Type")["Tips Earned"].mean().reset_index()
        shift_avg.columns = ["Shift Type", "Avg Tips"]
        shift_avg["Avg Tips"] = shift_avg["Avg Tips"].round(2)
        st.bar_chart(shift_avg.set_index("Shift Type"))

    # ── Tax & retirement ──────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("#### Tax & retirement summary (all time)")
    c12, c13, c14 = st.columns(3)
    c12.metric("Total tips earned",      f"${df['Tips Earned'].sum():,.2f}")
    c13.metric("Total tax to set aside", f"${df['Tax Set Aside'].sum():,.2f}")
    c14.metric("Total retirement",       f"${df['Retirement Set Aside'].sum():,.2f}")

    st.markdown("---")

    # ── Full shift log ────────────────────────────────────────────────────────
    st.markdown("#### All shifts")
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
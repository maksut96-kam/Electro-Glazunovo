import streamlit as st
import json
import os
import pandas as pd
from datetime import datetime, timedelta
import altair as alt

# --- КОНФИГУРАЦИЯ ---
SETTINGS_FILE = "official_data.json"
REPORT_DAY = 25 

def load_settings():
    default_date = datetime.now().date() - timedelta(days=5)
    default_data = {"day": 0.0, "night": 0.0, "date": default_date}
    if not os.path.exists(SETTINGS_FILE):
        return default_data
    try:
        with open(SETTINGS_FILE, "r") as f:
            content = f.read().strip()
            if not content: return default_data
            data = json.loads(content)
            saved_date = data.get("date")
            if isinstance(saved_date, str):
                try:
                    data["date"] = datetime.strptime(saved_date, "%Y-%m-%d").date()
                except ValueError:
                    data["date"] = default_date
            else:
                data["date"] = default_date
            data["day"] = float(data.get("day", 0.0))
            data["night"] = float(data.get("night", 0.0))
            return data
    except Exception:
        return default_data

def save_settings(day, night, date):
    with open(SETTINGS_FILE, "w") as f:
        json.dump({"day": day, "night": night, "date": str(date)}, f)

def calculate_precise_cost(d_kwh, n_kwh):
    total = d_kwh + n_kwh
    if total <= 0: return 0.0
    d_ratio = d_kwh / total
    n_ratio = n_kwh / total
    rates = [(8.39, 4.49), (11.41, 6.12), (16.70, 8.93)]
    cost = 0.0
    s1 = min(total, 1100)
    cost += s1 * d_ratio * rates[0][0] + s1 * n_ratio * rates[0][1]
    if total > 1100:
        s2 = min(total - 1100, 600)
        cost += s2 * d_ratio * rates[1][0] + s2 * n_ratio * rates[1][1]
    if total > 1700:
        s3 = total - 1700
        cost += s3 * d_ratio * rates[2][0] + s3 * n_ratio * rates[2][1]
    return cost

st.set_page_config(page_title="Электро-Глаз", page_icon="⚡", layout="wide")
st.title("⚡ Мониторинг электричества (Сочи)")

settings = load_settings()

with st.expander("⚙️ Настройка базы (официальные показания за 25-е число)"):
    off_date = st.date_input("Дата сдачи", value=settings["date"])
    c_off1, c_off2 = st.columns(2)
    off_day = c_off1.number_input("Базовый День", value=settings["day"])
    off_night = c_off2.number_input("Базовая Ночь", value=settings["night"])
    if st.button("💾 Сохранить базу"):
        save_settings(off_day, off_night, off_date)
        st.success("База обновлена!")
        st.rerun()

st.subheader(f"Текущий замер (отсчет от {settings['date']})")
col1, col2 = st.columns(2)
curr_day = col1.number_input("Показания День сейчас", value=off_day)
curr_night = col2.number_input("Показания Ночь сейчас", value=off_night)

delta_day = max(0.0, curr_day - off_day)
delta_night = max(0.0, curr_night - off_night)
total_kwh_now = delta_day + delta_night

today = datetime.now().date()
days_passed = max(1, (today - settings["date"]).days)
daily_avg = total_kwh_now / days_passed

if today.day >= REPORT_DAY:
    next_report = (today.replace(day=1) + timedelta(days=32)).replace(day=REPORT_DAY)
else:
    next_report = today.replace(day=REPORT_DAY)

total_days = (next_report - settings["date"]).days
projected_kwh = total_kwh_now + (daily_avg * (total_days - days_passed))

st.divider()
st.subheader("Текущее состояние")
m1, m2, m3 = st.columns(3)
m1.metric("Нагорело сейчас", f"{total_kwh_now:.1f} кВт")
m2.metric("Сумма к оплате", f"{calculate_precise_cost(delta_day, delta_night):.2f} ₽")
m3.metric("Среднее в сутки", f"{daily_avg:.1f} кВт")

st.divider()
st.subheader("📈 Прогноз к 25-му числу")
p1, p2, p3 = st.columns(3)
p1.metric("Итого к концу месяца", f"{projected_kwh:.0f} кВт")

ratio = delta_day / total_kwh_now if total_kwh_now > 0 else 0.5
proj_cost = calculate_precise_cost(projected_kwh * ratio, projected_kwh * (1-ratio))
p2.metric("Прогноз счета", f"{proj_cost:.2f} ₽")

if projected_kwh <= 1100:
    p3.success("Зона I (Оптимально)")
elif projected_kwh <= 1700:
    p3.warning("Зона II (Повышенная)")
else:
    p3.error("Зона III (Максимальная!)")

chart_df = pd.DataFrame({
    'day_idx': [0, days_passed, total_days],
    'value_kwh': [0, total_kwh_now, projected_kwh],
    'type': ['Start', 'Current', 'Forecast']
})

line = alt.Chart(chart_df).mark_line(point=True, color='orange').encode(
    x=alt.X('day_idx', title='Дней с начала периода'),
    y=alt.Y('value_kwh', title='Суммарно кВт'),
    tooltip=['type', 'value_kwh']
)

h1 = alt.Chart(pd.DataFrame({'y': [1100]})).mark_rule(color='green', strokeDash=[5,5]).encode(y='y')
h2 = alt.Chart(pd.DataFrame({'y': [1700]})).mark_rule(color='red', strokeDash=[5,5]).encode(y='y')

st.altair_chart(line + h1 + h2, use_container_width=True)

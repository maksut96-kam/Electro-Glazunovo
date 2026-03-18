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
    """Загрузка всех сохраненных данных (базовых и текущих)"""
    default_date = datetime.now().date() - timedelta(days=5)
    default_data = {
        "off_day": 0.0, "off_night": 0.0, "off_date": str(default_date),
        "curr_day": 0.0, "curr_night": 0.0
    }
    if not os.path.exists(SETTINGS_FILE):
        return default_data
    try:
        with open(SETTINGS_FILE, "r") as f:
            content = f.read().strip()
            if not content: return default_data
            data = json.loads(content)
            # Гарантируем наличие всех ключей
            for key in default_data:
                if key not in data: data[key] = default_data[key]
            return data
    except Exception:
        return default_data

def save_all_data(off_day, off_night, off_date, curr_day, curr_night):
    """Сохранение всех полей в один файл"""
    with open(SETTINGS_FILE, "w") as f:
        json.dump({
            "off_day": float(off_day),
            "off_night": float(off_night),
            "off_date": str(off_date),
            "curr_day": float(curr_day),
            "curr_night": float(curr_night)
        }, f)

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

data = load_settings()
base_date = datetime.strptime(data["off_date"], "%Y-%m-%d").date()

# --- БЛОК НАСТРОЕК БАЗЫ ---
with st.expander("⚙️ Настройка базы (официальные показания за 25-е число)"):
    new_off_date = st.date_input("Дата сдачи", value=base_date)
    c_off1, c_off2 = st.columns(2)
    new_off_day = c_off1.number_input("Базовый День", value=data["off_day"])
    new_off_night = c_off2.number_input("Базовая Ночь", value=data["off_night"])
    if st.button("💾 Обновить официальную базу"):
        save_all_data(new_off_day, new_off_night, new_off_date, data["curr_day"], data["curr_night"])
        st.success("База обновлена!")
        st.rerun()

# --- БЛОК ТЕКУЩИХ ПОКАЗАНИЙ ---
st.subheader(f"Текущий замер (отсчет от {base_date})")
col1, col2 = st.columns(2)
# Если текущие меньше базовых (например, новый месяц), подтягиваем базу
start_curr_day = max(data["curr_day"], data["off_day"])
start_curr_night = max(data["curr_night"], data["off_night"])

new_curr_day = col1.number_input("Показания День сейчас", value=start_curr_day)
new_curr_night = col2.number_input("Показания Ночь сейчас", value=start_curr_night)

# Кнопка сохранения текущих данных
if st.button("🔄 Сохранить текущие показания для всех"):
    save_all_data(data["off_day"], data["off_night"], data["off_date"], new_curr_day, new_curr_night)
    st.toast("Данные синхронизированы!")
    st.rerun()

# --- РАСЧЕТЫ ---
delta_day = max(0.0, new_curr_day - data["off_day"])
delta_night = max(0.0, new_curr_night - data["off_night"])
total_kwh_now = delta_day + delta_night

today = datetime.now().date()
days_passed = max(1, (today - base_date).days)
daily_avg = total_kwh_now / days_passed

if today.day >= REPORT_DAY:
    next_report = (today.replace(day=1) + timedelta(days=32)).replace(day=REPORT_DAY)
else:
    next_report = today.replace(day=REPORT_DAY)

total_days_in_period = (next_report - base_date).days
projected_kwh = total_kwh_now + (daily_avg * (total_days_in_period - days_passed))

# --- ВЫВОД МЕТРИК ---
st.divider()
m1, m2, m3 = st.columns(3)
m1.metric("Нагорело сейчас", f"{total_kwh_now:.1f} кВт")
m2.metric("Сумма к оплате", f"{calculate_precise_cost(delta_day, delta_night):.2f} ₽")
m3.metric("Среднее в сутки", f"{daily_avg:.1f} кВт")

st.divider()
st.subheader(f"📈 Прогноз к {next_report.strftime('%d.%m')}")
p1, p2, p3 = st.columns(3)
p1.metric("Итого к концу периода", f"{projected_kwh:.0f} кВт")

ratio = delta_day / total_kwh_now if total_kwh_now > 0 else 0.5
proj_cost = calculate_precise_cost(projected_kwh * ratio, projected_kwh * (1-ratio))
p2.metric("Прогноз счета", f"{proj_cost:.2f} ₽")

if projected_kwh <= 1100:
    p3.success("Зона I (Оптимально)")
elif projected_kwh <= 1700:
    p3.warning("Зона II (Повышенная)")
else:
    p3.error("Зона III (Максимальная!)")

# --- ГРАФИК С РЕАЛЬНЫМИ ДАТАМИ ---
chart_df = pd.DataFrame({
    'date': [pd.to_datetime(base_date), pd.to_datetime(today), pd.to_datetime(next_report)],
    'value_kwh': [0, total_kwh_now, projected_kwh],
    'type': ['Старт', 'Сегодня', 'Прогноз']
})

line = alt.Chart(chart_df).mark_line(point=True, color='orange').encode(
    x=alt.X('date:T', title='Дата'),
    y=alt.Y('value_kwh:Q', title='Суммарно кВт'),
    tooltip=[alt.Tooltip('date:T', title='Дата'), alt.Tooltip('value_kwh:Q', title='кВт')]
).properties(height=400)

h1 = alt.Chart(pd.DataFrame({'y': [1100]})).mark_rule(color='green', strokeDash=[5,5]).encode(y='y')
h2 = alt.Chart(pd.DataFrame({'y': [1700]})).mark_rule(color='red', strokeDash=[5,5]).encode(y='y')

st.altair_chart(line + h1 + h2, use_container_width=True)

import streamlit as st
import json
import os
import pandas as pd
from datetime import datetime, timedelta
import altair as alt

# --- КОНФИГУРАЦИЯ ---
SETTINGS_FILE = "all_property_data.json"
REPORT_DAY = 25 

def load_all_settings():
    """Загрузка данных для обоих объектов"""
    default_date = str(datetime.now().date() - timedelta(days=5))
    default_structure = {
        "house": {
            "off_day": 0.0, "off_night": 0.0, "off_date": default_date,
            "curr_day": 0.0, "curr_night": 0.0
        },
        "flat": {
            "off_day": 0.0, "off_date": default_date,
            "curr_day": 0.0
        }
    }
    if not os.path.exists(SETTINGS_FILE):
        return default_structure
    try:
        with open(SETTINGS_FILE, "r") as f:
            data = json.load(f)
            # Проверка структуры на случай старых версий файла
            if "house" not in data: return default_structure
            return data
    except Exception:
        return default_structure

def save_all_data(full_data):
    with open(SETTINGS_FILE, "w") as f:
        json.dump(full_data, f)

def calc_house_cost(d_kwh, n_kwh):
    """Ступенчатый тариф для Дома"""
    total = d_kwh + n_kwh
    if total <= 0: return 0.0
    d_ratio, n_ratio = d_kwh / total, n_kwh / total
    rates = [(8.39, 4.49), (11.41, 6.12), (16.70, 8.93)]
    cost = 0.0
    # Ступень 1
    s1 = min(total, 1100)
    cost += s1 * d_ratio * rates[0][0] + s1 * n_ratio * rates[0][1]
    # Ступень 2
    if total > 1100:
        s2 = min(total - 1100, 600)
        cost += s2 * d_ratio * rates[1][0] + s2 * n_ratio * rates[1][1]
    # Ступень 3
    if total > 1700:
        s3 = total - 1700
        cost += s3 * d_ratio * rates[2][0] + s3 * n_ratio * rates[2][1]
    return cost

def render_chart(base_date, today, next_report, current_val, projected_val, thresholds=None):
    chart_df = pd.DataFrame({
        'date': [pd.to_datetime(base_date), pd.to_datetime(today), pd.to_datetime(next_report)],
        'value_kwh': [0, current_val, projected_val],
        'type': ['Старт', 'Сегодня', 'Прогноз']
    })
    line = alt.Chart(chart_df).mark_line(point=True, color='orange').encode(
        x=alt.X('date:T', title='Дата'),
        y=alt.Y('value_kwh:Q', title='кВт всего'),
        tooltip=[alt.Tooltip('date:T', title='Дата'), alt.Tooltip('value_kwh:Q', title='кВт')]
    ).properties(height=350)
    
    final_chart = line
    if thresholds:
        for val, color in thresholds:
            rule = alt.Chart(pd.DataFrame({'y': [val]})).mark_rule(color=color, strokeDash=[5,5]).encode(y='y')
            final_chart += rule
    return final_chart

# --- ИНТЕРФЕЙС ---
st.set_page_config(page_title="Мониторинг электричества", page_icon="⚡", layout="wide")
st.title("⚡ Мониторинг электричества")

full_data = load_all_settings()
tab1, tab2 = st.tabs(["🏠 Дом Глазуново", "🏢 Кв. 300"])

# --- ВКЛАДКА 1: ДОМ ---
with tab1:
    h = full_data["house"]
    h_base_date = datetime.strptime(h["off_date"], "%Y-%m-%d").date()
    
    with st.expander("⚙️ Настройки базы (Дом)"):
        new_h_date = st.date_input("Дата базы (Дом)", value=h_base_date, key="h_date")
        c1, c2 = st.columns(2)
        new_h_off_d = c1.number_input("Баз. День", value=h["off_day"], key="h_off_d")
        new_h_off_n = c2.number_input("Баз. Ночь", value=h["off_night"], key="h_off_n")
        if st.button("Сохранить базу Дома"):
            full_data["house"].update({"off_day": new_h_off_d, "off_night": new_h_off_n, "off_date": str(new_h_date)})
            save_all_data(full_data); st.rerun()

    st.subheader(f"Текущий замер (Дом)")
    col_h1, col_h2 = st.columns(2)
    new_h_curr_d = col_h1.number_input("День сейчас", value=max(h["curr_day"], h["off_day"]), key="h_c_d")
    new_h_curr_n = col_h2.number_input("Ночь сейчас", value=max(h["curr_night"], h["off_night"]), key="h_c_n")
    
    if st.button("🔄 Синхронизировать Дом"):
        full_data["house"].update({"curr_day": new_h_curr_d, "curr_night": new_h_curr_n})
        save_all_data(full_data); st.toast("Дом обновлен!"); st.rerun()

    d_d, d_n = new_h_curr_d - h["off_day"], new_h_curr_n - h["off_night"]
    total_h = d_d + d_n
    days_p = max(1, (datetime.now().date() - h_base_date).days)
    # Прогноз
    next_rep = (datetime.now().date().replace(day=REPORT_DAY) if datetime.now().day < REPORT_DAY else (datetime.now().date().replace(day=1)+timedelta(days=32)).replace(day=REPORT_DAY))
    proj_h = total_h + ((total_h/days_p) * ((next_rep - h_base_date).days - days_p))
    
    m1, m2, m3 = st.columns(3)
    m1.metric("Нагорело", f"{total_h:.1f} кВт")
    m2.metric("К оплате", f"{calc_house_cost(d_d, d_n):.2f} ₽")
    m3.metric("Прогноз", f"{proj_h:.0f} кВт")
    
    st.altair_chart(render_chart(h_base_date, datetime.now().date(), next_rep, total_h, proj_h, [(1100, 'green'), (1700, 'red')]), use_container_width=True)

# --- ВКЛАДКА 2: КВАРТИРА ---
with tab2:
    f = full_data["flat"]
    f_base_date = datetime.strptime(f["off_date"], "%Y-%m-%d").date()
    
    with st.expander("⚙️ Настройки базы (Квартира)"):
        new_f_date = st.date_input("Дата базы (Кв)", value=f_base_date, key="f_date")
        new_f_off = st.number_input("Базовые показания", value=f["off_day"], key="f_off")
        if st.button("Сохранить базу Квартиры"):
            full_data["flat"].update({"off_day": new_f_off, "off_date": str(new_f_date)})
            save_all_data(full_data); st.rerun()

    st.subheader("Текущий замер (Кв. 300)")
    new_f_curr = st.number_input("Показания сейчас", value=max(f["curr_day"], f["off_day"]), key="f_c_d")
    
    if st.button("🔄 Синхронизировать Квартиру"):
        full_data["flat"].update({"curr_day": new_f_curr})
        save_all_data(full_data); st.toast("Квартира обновлена!"); st.rerun()

    delta_f = new_f_curr - f["off_day"]
    days_p_f = max(1, (datetime.now().date() - f_base_date).days)
    proj_f = delta_f + ((delta_f/days_p_f) * ((next_rep - f_base_date).days - days_p_f))
    
    m1f, m2f, m3f = st.columns(3)
    m1f.metric("Нагорело", f"{delta_f:.1f} кВт")
    m2f.metric("К оплате (5.24₽)", f"{delta_f * 5.24:.2f} ₽")
    m3f.metric("Прогноз", f"{proj_f:.0f} кВт")
    
    st.altair_chart(render_chart(f_base_date, datetime.now().date(), next_rep, delta_f, proj_f), use_container_width=True)

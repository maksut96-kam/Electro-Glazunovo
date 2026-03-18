import streamlit as st
import json
import os
import pandas as pd
from datetime import datetime, timedelta
import altair as alt

# --- НАСТРОЙКИ И БАЗА ДАННЫХ ---
SETTINGS_FILE = "official_data.json"
# День сдачи показаний (каждый месяц)
REPORT_DAY = 25

# Функция загрузки базовых показаний
def load_settings():
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, "r") as f:
            data = json.load(f)
            # Конвертируем строку даты обратно в объект даты
            data["date"] = datetime.strptime(data["date"], "%Y-%m-%d").date()
            return data
    # Дефолт на случай, если файла нет
    return {"day": 0.0, "night": 0.0, "date": (datetime.now().date() - timedelta(days=5))}

# Функция сохранения базовых показаний
def save_settings(day, night, date):
    with open(SETTINGS_FILE, "w") as f:
        json.dump({"day": day, "night": night, "date": str(date)}, f)

# --- ЛОГИКА ТАРИФНЫХ СТУПЕНЕЙ ---
def calculate_precise_cost(d_kwh, n_kwh):
    total = d_kwh + n_kwh
    if total <= 0: return 0.0
    
    # Распределение (День / Ночь)
    d_ratio = d_kwh / total
    n_ratio = n_kwh / total

    # Тарифы Сочи (День, Ночь)
    rates = [
        (8.39, 4.49),   # I: до 1100
        (11.41, 6.12),  # II: 1100 - 1700
        (16.70, 8.93)   # III: свыше 1700
    ]
    
    cost = 0.0
    
    # 1 ступень (0 - 1100)
    s1_limit = 1100
    s1 = min(total, s1_limit)
    cost += s1 * d_ratio * rates[0][0] + s1 * n_ratio * rates[0][1]
    
    # 2 ступень (1100 - 1700)
    s2_limit = 1700
    if total > s1_limit:
        s2 = min(total - s1_limit, s2_limit - s1_limit) # Максимум 600 кВт в этом окне
        cost += s2 * d_ratio * rates[1][0] + s2 * n_ratio * rates[1][1]
        
    # 3 ступень (свыше 1700)
    if total > s2_limit:
        s3 = total - s2_limit
        cost += s3 * d_ratio * rates[2][0] + s3 * n_ratio * rates[2][1]
        
    return cost

# --- КОНФИГУРАЦИЯ СТРАНИЦЫ ИНТЕРФЕЙСА ---
st.set_page_config(page_title="Энерго-Контроль Сочи", page_icon="⚡", layout="wide")
st.title("⚡ Мониторинг затрат на свет")

# --- ЗАГРУЗКА И НАСТРОЙКА ОФИЦИАЛЬНОЙ БАЗЫ ---
settings = load_settings()

with st.expander("📝 Настройка официальных показаний (база за 25-е число)"):
    st.write("Эти данные сохранятся и будут основой для расчета до следующего месяца.")
    
    # Определяем дефолтную дату сдачи для выбора
    default_date = settings["date"]
    
    off_date = st.date_input("Дата сдачи", value=default_date)
    col_off1, col_off2 = st.columns(2)
    off_day = col_off1.number_input("Офиц. День (счетчик)", value=float(settings["day"]))
    off_night = col_off2.number_input("Офиц. Ночь (счетчик)", value=float(settings["night"]))
    
    if st.button("💾 Сохранить как новую базу"):
        save_settings(off_day, off_night, off_date)
        st.success(f"Данные обновлены! Теперь считаем от {off_date}")
        st.rerun()

# --- ТЕКУЩИЕ ЗАМЕРЫ И РАСЧЕТЫ ---
st.subheader(f"Текущие замеры (считаем от базы за {settings['date']})")
main_c1, main_c2 = st.columns(2)
curr_day = main_c1.number_input("Текущий День (показания сейчас)", value=off_day)
curr_night = main_c2.number_input("Текущая Ночь (показания сейчас)", value=off_night)

# Даты для прогноза
today = datetime.now().date()
# Прошло дней с момента сдачи базовых показаний
days_passed = max(1, (today - settings["date"]).days)

# Расчет потребления (дельты)
delta_day = max(0.0, curr_day - off_day)
delta_night = max(0.0, curr_night - off_night)
total_kwh_now = delta_day + delta_night

# Среднее потребление в день
daily_avg = total_kwh_now / days_passed

# Дата следующей сдачи (25 число следующего или текущего месяца)
if today.day >= REPORT_DAY:
    next_report_date = (today.replace(day=1) + timedelta(days=32)).replace(day=REPORT_DAY)
else:
    next_report_date = today.replace(day=REPORT_DAY)
    
# Всего дней в расчетном периоде
total_days_in_period = (next_report_date - settings["date"]).days

# Расчет стоимости
total_cost_now = calculate_precise_cost(delta_day, delta_night)

# --- ВЫВОД РЕЗУЛЬТАТОВ НА МЕТРИКИ ---
st.divider()
st.subheader("Текущее состояние")
res1, res2, res3 = st.columns(3)
res1.metric("Нагорело всего", f"{total_kwh_now:.1f} кВт")
res2.metric("Сумма к оплате", f"{total_cost_now:.2f} ₽")
res3.metric("Среднее в день", f"{daily_avg:.1f} кВт/день", help=f"За последние {days_passed} дней")

# Визуализация текущей зоны
if total_kwh_now <= 1100:
    st.success("Вы в 1-м диапазоне (Базовый тариф)")
elif total_kwh_now <= 1700:
    st.warning("Внимание: 2-й диапазон (Повышенный тариф)")
else:
    st.error("🚨 3-й диапазон (Максимальный тариф!)")

# Прогресс бар
st.progress(min(total_kwh_now / 2000.0, 1.0)) # 2000 кВт как условный максимум шкалы

# --- ЛОГИКА И ГРАФИК ПРОГНОЗА ---
st.divider()
st.subheader("📈 Прогноз на конец периода (до 25 числа)")

# Расчет прогнозируемого потребления к концу месяца
projected_kwh_total = total_kwh_now + (daily_avg * (total_days_in_period - days_passed))

# Расчет прогнозируемой стоимости
# Мы предполагаем, что пропорция день/ночь сохранится такой же
proj_ratio_day = delta_day / total_kwh_now if total_kwh_now > 0 else 0.5
proj_kwh_day = projected_kwh_total * proj_ratio_day
proj_kwh_night = projected_kwh_total * (1 - proj_ratio_day)
projected_cost_total = calculate_precise_cost(proj_kwh_day, proj_kwh_night)

# Метрики прогноза
p1, p2, p3 = st.columns(3)
p1.metric("Прогноз к 25 числу", f"{projected_kwh_total:.0f} кВт", f"{projected_kwh_total - total_kwh_now:.0f} кВт еще")
p2.metric("Прогноз счета", f"{projected_cost_total:.2f} ₽", f"{calculate_precise_cost(daily_avg * (total_days_in_period - days_passed) * proj_ratio_day, daily_avg * (total_days_in_period - days_passed) * (1 - proj_ratio_day)):.2f} ₽ к текущему", delta_color="inverse")

# Диагноз прогноза
if projected_kwh_total <= 1100:
    p3.success("Прогноз: Зона I")
elif projected_kwh_total <= 1700:
    p3.warning("Прогноз: Перейдете в Зону II")
else:
    p3.error("🚨 Прогноз: Перейдете в Зону III!")

# --- ПОСТРОЕНИЕ ГРАФИКА ПРОГНОЗА (Altair) ---
# Создаем DataFrame для графика
chart_data = pd.DataFrame({
    'День': [days_passed, total_days_in_period],
    'кВт': [total_kwh_now, projected_kwh_total],
    'Тип': ['Текущее', 'Прогноз']
})

# Настройка графика
chart = alt.Chart(chart_data).mark_line(point=True, color='orange').encode(
    x=alt.X('День', axis=alt.Axis(title='День с начала периода')),
    y=alt.Y('кВт', axis=alt.Axis(title='Суммарное потребление (кВт)')),
    tooltip=['День', 'кВт', 'Тип']
).properties(
    title=f"Прогноз роста потребления (до {total_days_in_period} дней)"
).interactive()

# Добавляем горизонтальные линии тарифных зон
zone1_line = alt.Chart(pd.DataFrame({'y': [1100]})).mark_rule(color='green', strokeDash=[5, 5]).encode(y='y')
zone2_line = alt.Chart(pd.DataFrame({'y': [1700]})).mark_rule(color='red', strokeDash=[5, 5]).encode(y='y')

# Добавляем текст над линиями зон
zone1_text = alt.Chart(pd.DataFrame({'y': [1100], 'x': [total_days_in_period - 2], 'text': ['Порог II зоны']})).mark_text(dy=-5, color='green').encode(x='x', y='y', text='text')
zone2_text = alt.Chart(pd.DataFrame({'y': [1700], 'x': [total_days_in_period - 2], 'text': ['Порог III зоны']})).mark_text(dy=-5, color='red').encode(x='x', y='y', text='text')

# Компонуем график
st.altair_chart(chart + zone1_line + zone2_line + zone1_text + zone2_text, use_container_width=True)

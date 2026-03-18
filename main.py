import streamlit as st
import json
import os
import pandas as pd
from datetime import datetime, timedelta
import altair as alt

# --- КОНФИГУРАЦИЯ ---
SETTINGS_FILE = "official_data.json"
REPORT_DAY = 25  # Число месяца для сдачи показаний

def load_settings():
    """Безопасная загрузка настроек с защитой от пустых файлов и ошибок ключей"""
    default_date = datetime.now().date() - timedelta(days=5)
    default_data = {
        "day": 0.0, 
        "night": 0.0, 
        "date": default_date
    }
    
    if not os.path.exists(SETTINGS_FILE):
        return default_data
        
    try:
        with open(SETTINGS_FILE, "r") as f:
            content = f.read().strip()
            if not content:
                return default_data
            
            data = json.loads(content)
            
            # Проверка и конвертация даты
            saved_date = data.get("date")
            if isinstance(saved_date, str):
                try:
                    data["date"] = datetime.strptime(saved_date, "%Y-%m-%d").date()
                except ValueError:
                    data["date"] = default_date
            else:
                data["date"] = default_date
                
            # Проверка чисел
            data["day"] = float(data.get("day", 0.0))
            data["night"] = float(data.get("night", 0.0))
            
            return data
    except Exception:
        return default_data

def save_settings(day, night, date):
    """Сохранение данных в JSON"""
    with open(SETTINGS_FILE, "w") as f:
        json.dump({"day": day, "night": night, "date": str(date)}, f)

def calculate_precise_cost(d_kwh, n_kwh):
    """Логика трех диапазонов Сочи"""
    total = d_kwh + n_kwh
    if total <= 0: return 0.0
    
    d_ratio = d_kwh / total
    n_ratio = n_kwh / total

    # Тарифы: (День, Ночь)
    rates = [
        (8.39, 4.49),   # I: 0 - 1100
        (11.41, 6.12),  # II: 1100 - 1700
        (16.70, 8.93)   # III: 1700+
    ]
    
    cost = 0.0
    # Ступень 1 (до 1100)
    s1 = min(total, 1100)
    cost += s1 * d_ratio * rates[0][0] + s1 * n_ratio * rates[0][1]
    
    # Ступень 2 (1100 - 1700)
    if total > 1100:
        s2 = min(total - 1100, 600)
        cost += s2 * d_ratio * rates[1][0] + s2 * n_ratio * rates[1][1]
        
    # Ступень 3 (свыше 1700)
    if total > 1700:
        s3 = total - 1700
        cost += s3 * d_ratio * rates[2][0] + s3 * n_ratio * rates[2][1]
        
    return cost

# --- ИНТЕРФЕЙС ---
st.set_page_config(page_title="Электро-Глаз", page_icon="⚡", layout

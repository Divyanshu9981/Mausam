#!/usr/bin/env python3
"""
mausam.py — India Weather App (End-to-End Python)
==================================================
Runs a local web server that:
  1. Proxies Open-Meteo API calls (fixes the CORS/file:// fetch error)
  2. Serves the full weather web app on http://localhost:8888
  3. Auto-opens your browser

Usage:
    python mausam.py

Requirements: Python 3.7+  (zero extra packages — stdlib only)
"""

import http.server
import urllib.request
import urllib.parse
import json
import threading
import webbrowser
import sys
import os

PORT = 8502

# ── Full HTML app (embedded so it's truly one file) ───────────────────────────
HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>मौसम — India Weather</title>
<link href="https://fonts.googleapis.com/css2?family=Baloo+2:wght@400;500;600;700;800&family=Noto+Sans:wght@300;400;500&display=swap" rel="stylesheet">
<style>
:root {
  --saffron: #FF6B00; --turmeric: #F5A623; --sky: #4FC3F7;
  --rain: #1565C0;    --heat: #BF360C;    --sub: #5C5C7A;
  --bg: #FFF8F0;      --card: #FFFFFF;    --text: #1A1A2E;
  --border: #EDE0D4;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: 'Noto Sans', sans-serif;
  background: var(--bg); color: var(--text);
  min-height: 100vh; overflow-x: hidden;
}
body::before {
  content: ''; position: fixed; inset: 0; pointer-events: none; z-index: 0;
  background:
    radial-gradient(circle at 20% 20%, rgba(255,107,0,0.06) 0%, transparent 50%),
    radial-gradient(circle at 80% 80%, rgba(79,195,247,0.07) 0%, transparent 50%),
    radial-gradient(circle at 50% 50%, rgba(245,166,35,0.04) 0%, transparent 60%);
}
.app { position: relative; z-index: 1; max-width: 920px; margin: 0 auto; padding: 0 16px 60px; }

/* ── Header ── */
header {
  padding: 28px 0 20px;
  display: flex; align-items: center; justify-content: space-between;
  flex-wrap: wrap; gap: 12px;
}
.brand-title {
  font-family: 'Baloo 2', cursive; font-size: 38px;
  font-weight: 800; color: var(--saffron); line-height: 1; letter-spacing: -1px;
}
.brand-sub {
  font-size: 11px; color: var(--sub);
  letter-spacing: 0.14em; text-transform: uppercase; margin-top: 3px;
}
.city-picker {
  display: flex; align-items: center; gap: 8px;
  background: var(--card); border: 1.5px solid var(--border);
  border-radius: 50px; padding: 8px 16px 8px 12px;
  box-shadow: 0 2px 12px rgba(0,0,0,0.06);
}
.city-picker select {
  border: none; background: transparent;
  font-family: 'Noto Sans', sans-serif; font-size: 14px;
  font-weight: 500; color: var(--text); cursor: pointer; outline: none;
}

/* ── Loading / Error ── */
#loading {
  display: flex; flex-direction: column;
  align-items: center; justify-content: center;
  min-height: 320px; gap: 16px;
}
.spinner {
  width: 44px; height: 44px;
  border: 3px solid var(--border); border-top-color: var(--saffron);
  border-radius: 50%; animation: spin 0.8s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }
.loading-text { color: var(--sub); font-size: 14px; }
#error {
  display: none; background: #FFF3E0;
  border: 1.5px solid #FFB74D; border-radius: 14px;
  padding: 20px; color: #E65100; font-size: 14px; text-align: center; margin-top: 20px;
}
#content { display: none; }

/* ── Today hero ── */
.today-card {
  background: linear-gradient(135deg, var(--saffron) 0%, var(--turmeric) 100%);
  border-radius: 24px; padding: 28px; color: white;
  position: relative; overflow: hidden;
  box-shadow: 0 8px 32px rgba(255,107,0,0.25);
  margin-bottom: 16px; animation: fadeUp 0.4s ease both;
}
.today-card::after {
  content: ''; position: absolute; right: -40px; top: -40px;
  width: 220px; height: 220px; border-radius: 50%;
  background: rgba(255,255,255,0.08); pointer-events: none;
}
.today-top {
  display: flex; justify-content: space-between;
  align-items: flex-start; flex-wrap: wrap; gap: 12px;
}
.today-location { font-size: 13px; opacity: 0.85; letter-spacing: 0.1em; text-transform: uppercase; }
.today-date     { font-size: 13px; opacity: 0.75; margin-top: 3px; }
.today-desc     { font-size: 18px; font-weight: 500; margin-top: 8px; opacity: 0.9; }
.today-minmax   { font-size: 13px; opacity: 0.75; margin-top: 4px; }
.today-right    { display: flex; flex-direction: column; align-items: flex-end; gap: 4px; }
.today-emoji    { font-size: 56px; filter: drop-shadow(0 4px 8px rgba(0,0,0,0.15)); }
.today-temp-block { display: flex; align-items: flex-start; }
.today-temp {
  font-family: 'Baloo 2', cursive; font-size: 88px;
  font-weight: 800; line-height: 1; letter-spacing: -4px;
}
.today-unit { font-size: 28px; margin-top: 12px; opacity: 0.7; }
.today-stats {
  display: flex; gap: 20px; margin-top: 20px;
  padding-top: 18px; border-top: 1px solid rgba(255,255,255,0.2); flex-wrap: wrap;
}
.stat-label { font-size: 10px; opacity: 0.7; text-transform: uppercase; letter-spacing: 0.1em; }
.stat-val   { font-size: 16px; font-weight: 600; margin-top: 2px; }

/* ── Advisory row ── */
.advisory-row {
  display: grid; grid-template-columns: 1fr 1fr;
  gap: 12px; margin-bottom: 16px;
  animation: fadeUp 0.4s 0.1s ease both;
}
@media (max-width: 560px) { .advisory-row { grid-template-columns: 1fr; } }
.advisory-card {
  background: var(--card); border: 1.5px solid var(--border);
  border-radius: 18px; padding: 20px;
  box-shadow: 0 2px 12px rgba(0,0,0,0.04);
}
.adv-label {
  font-size: 10px; text-transform: uppercase;
  letter-spacing: 0.15em; color: var(--sub); margin-bottom: 10px; font-weight: 500;
}
.adv-main  { display: flex; align-items: center; gap: 12px; margin-bottom: 8px; }
.adv-icon  { font-size: 36px; }
.adv-title {
  font-family: 'Baloo 2', cursive; font-size: 20px;
  font-weight: 700; color: var(--text); line-height: 1.2;
}
.adv-reason { font-size: 12px; color: var(--sub); line-height: 1.6; }
.food-chips { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 10px; }
.food-chip {
  background: var(--bg); border: 1px solid var(--border);
  border-radius: 50px; padding: 4px 12px;
  font-size: 12px; color: var(--text); font-weight: 500;
}

/* ── Section title ── */
.section-title {
  font-family: 'Baloo 2', cursive; font-size: 20px; font-weight: 700;
  color: var(--text); margin: 24px 0 12px;
  display: flex; align-items: center; gap: 8px;
  animation: fadeUp 0.4s 0.15s ease both;
}

/* ── Hourly strip ── */
.hourly-strip {
  display: flex; gap: 8px; overflow-x: auto; padding-bottom: 8px;
  scrollbar-width: thin; scrollbar-color: var(--border) transparent;
  animation: fadeUp 0.4s 0.2s ease both;
}
.hourly-strip::-webkit-scrollbar { height: 4px; }
.hourly-strip::-webkit-scrollbar-thumb { background: var(--border); border-radius: 2px; }
.hour-card {
  flex: 0 0 70px; background: var(--card);
  border: 1.5px solid var(--border); border-radius: 12px;
  padding: 10px 6px; display: flex; flex-direction: column;
  align-items: center; gap: 5px;
}
.hour-card.now { border-color: var(--saffron); background: rgba(255,107,0,0.04); }
.hour-time { font-size: 10px; color: var(--sub); font-weight: 500; }
.hour-icon { font-size: 22px; }
.hour-temp { font-size: 14px; font-weight: 700; color: var(--text); }
.hour-rain { font-size: 10px; color: var(--rain); min-height: 14px; }

/* ── 10-day forecast ── */
.forecast-grid {
  display: flex; flex-direction: column; gap: 8px;
  animation: fadeUp 0.4s 0.25s ease both;
}
.forecast-row {
  background: var(--card); border: 1.5px solid var(--border);
  border-radius: 14px; padding: 14px 18px;
  display: grid; grid-template-columns: 100px 40px 1fr 70px 36px;
  align-items: center; gap: 12px;
  transition: transform 0.15s, box-shadow 0.15s;
}
.forecast-row:hover { transform: translateX(4px); box-shadow: 0 4px 16px rgba(0,0,0,0.07); }
.forecast-row.today-row { border-color: var(--saffron); background: rgba(255,107,0,0.03); }
@media (max-width: 560px) {
  .forecast-row { grid-template-columns: 80px 36px 1fr 60px; }
  .fc-umbrella { display: none; }
}
.fc-day     { font-size: 13px; font-weight: 600; }
.fc-day-sub { font-size: 11px; color: var(--sub); }
.fc-icon    { font-size: 26px; text-align: center; }
.fc-bar-wrap { height: 6px; background: var(--border); border-radius: 3px; }
.fc-bar     { height: 100%; border-radius: 3px; background: linear-gradient(90deg, #4FC3F7, #FF6B00); }
.fc-rain-label { font-size: 10px; color: var(--rain); margin-top: 3px; }
.fc-temps   { display: flex; flex-direction: column; align-items: flex-end; gap: 2px; }
.fc-max     { font-size: 15px; font-weight: 700; color: var(--heat); }
.fc-min     { font-size: 12px; color: var(--sky); --sky: #4FC3F7; color: #1565C0; }

/* ── Footer ── */
footer {
  text-align: center; padding: 32px 0 0;
  font-size: 11px; color: var(--sub);
  border-top: 1px solid var(--border); margin-top: 32px;
}
footer a { color: var(--saffron); text-decoration: none; }

@keyframes fadeUp {
  from { opacity: 0; transform: translateY(14px); }
  to   { opacity: 1; transform: translateY(0); }
}
</style>
</head>
<body>
<div class="app">
  <header>
    <div>
      <div class="brand-title">मौसम</div>
      <div class="brand-sub">India Weather · Open-Meteo · Python Server</div>
    </div>
    <div class="city-picker">
      <span>📍</span>
      <select id="citySelect" onchange="loadCity()">
        <option value="28.61,77.21,New Delhi">New Delhi</option>
        <option value="26.85,80.92,Lucknow" selected>Lucknow</option>
        <option value="19.08,72.88,Mumbai">Mumbai</option>
        <option value="22.57,88.36,Kolkata">Kolkata</option>
        <option value="13.08,80.27,Chennai">Chennai</option>
        <option value="12.97,77.59,Bengaluru">Bengaluru</option>
        <option value="17.38,78.47,Hyderabad">Hyderabad</option>
        <option value="23.02,72.57,Ahmedabad">Ahmedabad</option>
        <option value="18.52,73.85,Pune">Pune</option>
        <option value="26.92,75.82,Jaipur">Jaipur</option>
        <option value="21.17,72.83,Surat">Surat</option>
        <option value="30.73,76.78,Chandigarh">Chandigarh</option>
        <option value="25.59,85.13,Patna">Patna</option>
        <option value="21.25,81.63,Raipur">Raipur</option>
        <option value="23.18,77.39,Bhopal">Bhopal</option>
        <option value="8.52,76.94,Thiruvananthapuram">Thiruvananthapuram</option>
        <option value="26.21,92.94,Guwahati">Guwahati</option>
        <option value="27.10,88.26,Gangtok">Gangtok</option>
        <option value="34.08,74.80,Srinagar">Srinagar</option>
        <option value="32.22,76.32,Dharamshala">Dharamshala</option>
      </select>
    </div>
  </header>

  <div id="loading">
    <div class="spinner"></div>
    <div class="loading-text">Fetching live weather…</div>
  </div>
  <div id="error">⚠️ <span id="errMsg">Something went wrong.</span></div>

  <div id="content">
    <div class="today-card" id="todayCard">
      <div class="today-top">
        <div>
          <div class="today-location" id="todayCity"></div>
          <div class="today-date"     id="todayDate"></div>
          <div class="today-desc"     id="todayDesc"></div>
          <div class="today-minmax"   id="todayMinMax"></div>
        </div>
        <div class="today-right">
          <div class="today-emoji" id="todayEmoji"></div>
          <div class="today-temp-block">
            <div class="today-temp" id="todayTemp"></div>
            <div class="today-unit">°C</div>
          </div>
        </div>
      </div>
      <div class="today-stats">
        <div><div class="stat-label">Feels like</div><div class="stat-val" id="feelsLike"></div></div>
        <div><div class="stat-label">Humidity</div><div class="stat-val" id="humidity"></div></div>
        <div><div class="stat-label">Wind</div><div class="stat-val" id="wind"></div></div>
        <div><div class="stat-label">Rain chance</div><div class="stat-val" id="rainChance"></div></div>
        <div><div class="stat-label">UV Index</div><div class="stat-val" id="uvIndex"></div></div>
      </div>
    </div>

    <div class="advisory-row">
      <div class="advisory-card" id="umbCard">
        <div class="adv-label">☂ Umbrella advisory</div>
        <div class="adv-main">
          <div class="adv-icon"  id="umbIcon"></div>
          <div class="adv-title" id="umbTitle"></div>
        </div>
        <div class="adv-reason" id="umbReason"></div>
      </div>
      <div class="advisory-card" id="foodCard">
        <div class="adv-label">🍽 What to eat today</div>
        <div class="adv-main">
          <div class="adv-icon"  id="foodIcon"></div>
          <div class="adv-title" id="foodMood"></div>
        </div>
        <div class="adv-reason" id="foodReason"></div>
        <div class="food-chips" id="foodChips"></div>
      </div>
    </div>

    <div class="section-title">⏱ Today's hourly</div>
    <div class="hourly-strip" id="hourlyStrip"></div>

    <div class="section-title">📅 10-day forecast</div>
    <div class="forecast-grid" id="forecastGrid"></div>
  </div>

  <footer>
    Data from <a href="https://open-meteo.com" target="_blank">Open-Meteo</a> (free, no API key) ·
    Served by Python on localhost:PORT_PLACEHOLDER
  </footer>
</div>

<script>
// ── WMO weather codes ──────────────────────────────────────────────────────────
const WMO = {
  0:['Clear sky','☀️'],   1:['Mostly clear','🌤'],  2:['Partly cloudy','⛅'],
  3:['Overcast','☁️'],    45:['Foggy','🌫'],         48:['Icy fog','🌫'],
  51:['Light drizzle','🌦'], 53:['Drizzle','🌦'],    55:['Heavy drizzle','🌧'],
  61:['Light rain','🌧'],    63:['Rain','🌧'],        65:['Heavy rain','🌧'],
  71:['Light snow','🌨'],    73:['Snow','❄️'],        75:['Heavy snow','❄️'],
  80:['Light showers','🌦'], 81:['Showers','🌧'],    82:['Heavy showers','⛈'],
  95:['Thunderstorm','⛈'],  96:['Storm+hail','⛈'],  99:['Storm+hail','⛈'],
};
const wmo = c => WMO[c] || ['Unknown','🌡'];

// ── Food engine ────────────────────────────────────────────────────────────────
function foodAdvice(code, tmax, hum, rainPct) {
  const rainy  = [51,53,55,61,63,65,80,81,82,95,96,99].includes(code) || rainPct > 50;
  const stormy = [82,95,96,99].includes(code);
  const foggy  = [45,48].includes(code);
  const hot    = tmax >= 35, warm = tmax >= 28, cool = tmax < 22, cold = tmax < 15;
  const humid  = hum > 75;

  if (stormy || (rainy && humid)) return {
    icon:'🧅', mood:'Pakora & chai weather!',
    reason:'Heavy rain + humidity = perfect excuse for hot crispy pakoras with masala chai.',
    chips:['🧅 Pyaaz pakora','🫚 Samosa','☕ Masala chai','🍚 Khichdi','🫘 Dal tadka']
  };
  if (rainy) return {
    icon:'🫘', mood:'Cozy comfort food',
    reason:'Rainy day — warm, soul-filling meals only. Avoid raw salads.',
    chips:['🫘 Dal chawal','☕ Adrak chai','🧅 Pakora','🥣 Khichdi','🍞 Puri sabzi']
  };
  if (cold) return {
    icon:'🍲', mood:'Hearty winter meals',
    reason:`At ${tmax}°C your body needs warming, ghee-rich, high-protein food.`,
    chips:['🫕 Sarson saag','🌽 Makki roti','🫘 Rajma chawal','🍯 Gond ladoo','☕ Kahwa']
  };
  if (cool) return {
    icon:'🥘', mood:'Light warm meals',
    reason:'Pleasantly cool — light sabzis and dals. Skip ice cream & cold drinks.',
    chips:['🥬 Palak paneer','🫘 Moong dal','🍞 Roti','☕ Masala chai','🥕 Gajar halwa']
  };
  if (hot && humid) return {
    icon:'🥤', mood:'Cool hydrating foods',
    reason:`Hot (${tmax}°C) + humid (${hum}%) — light food, lots of water.`,
    chips:['🥒 Raita','🍋 Nimbu paani','🌊 Coconut water','🍉 Tarbuz','🧆 Curd rice']
  };
  if (hot) return {
    icon:'🥭', mood:'Beat the heat!',
    reason:`It's ${tmax}°C — stay hydrated with cooling foods and plenty of fluids.`,
    chips:['🥭 Aam panna','🍋 Nimbu paani','🥛 Lassi','🍚 Curd rice','🌿 Mint chutney']
  };
  if (foggy) return {
    icon:'☕', mood:'Warm foggy morning',
    reason:'Fog makes you sluggish — something warm and light to kickstart the day.',
    chips:['☕ Masala chai','🥚 Egg paratha','🍶 Daliya','🫘 Moong chilla','🧈 Roti makkhan']
  };
  return {
    icon:'🍱', mood:'Great day to eat well!',
    reason:'Comfortable weather — enjoy a full balanced thali.',
    chips:['🍱 Full thali','🥗 Kachumber','🫘 Dal makhani','🍚 Biryani','🥛 Buttermilk']
  };
}

// ── Umbrella engine ────────────────────────────────────────────────────────────
function umbAdvice(code, rainPct, rainMm) {
  const heavy  = [65,82,95,96,99].includes(code) || rainMm > 10;
  const raining= [51,53,55,61,63,65,80,81,82,95,96,99].includes(code);
  if (heavy)              return {icon:'☂️', title:'Definitely carry!',  color:'#1565C0', reason:`Heavy rain (${rainMm.toFixed(1)}mm). Don't step out without one.`};
  if (raining||rainPct>=40) return {icon:'🌂', title:'Yes, carry it',     color:'#1976D2', reason:`${rainPct}% rain chance. Better safe than soggy.`};
  if (rainPct >= 20)        return {icon:'🤔', title:'Maybe, just in case',color:'#5C5C7A', reason:`Low chance (${rainPct}%) but skies look uncertain.`};
  return                         {icon:'✅', title:'No need today!',     color:'#2E7D32', reason:'Clear skies — leave the umbrella at home.'};
}

// ── Render ─────────────────────────────────────────────────────────────────────
function render(data, cityName) {
  const cur = data.current, h = data.hourly, d = data.daily;
  const now = new Date();

  // Hero
  const [desc, emoji] = wmo(cur.weather_code);
  const tmax = Math.round(d.temperature_2m_max[0]);
  const tmin = Math.round(d.temperature_2m_min[0]);
  const rainPct = d.precipitation_probability_max[0];
  const rainMm  = d.precipitation_sum[0];

  document.getElementById('todayCity').textContent  = `📍 ${cityName}`;
  document.getElementById('todayDate').textContent  = now.toLocaleDateString('en-IN',{weekday:'long',day:'numeric',month:'long',year:'numeric'});
  document.getElementById('todayTemp').textContent  = Math.round(cur.temperature_2m);
  document.getElementById('todayDesc').textContent  = desc;
  document.getElementById('todayMinMax').textContent= `↑ ${tmax}°  ↓ ${tmin}°`;
  document.getElementById('todayEmoji').textContent = emoji;
  document.getElementById('feelsLike').textContent  = `${Math.round(cur.apparent_temperature)}°C`;
  document.getElementById('humidity').textContent   = `${cur.relative_humidity_2m}%`;
  document.getElementById('wind').textContent       = `${Math.round(cur.wind_speed_10m)} km/h`;
  document.getElementById('rainChance').textContent = `${rainPct}%`;
  document.getElementById('uvIndex').textContent    = cur.uv_index ?? '—';

  // Card gradient based on conditions
  const card = document.getElementById('todayCard');
  const t = cur.temperature_2m;
  const c = cur.weather_code;
  card.style.background =
    [95,96,99,82].includes(c)    ? 'linear-gradient(135deg,#1A237E,#283593)' :
    [61,63,65,80,81].includes(c) ? 'linear-gradient(135deg,#0D47A1,#1565C0)' :
    [51,53,55].includes(c)       ? 'linear-gradient(135deg,#37474F,#455A64)' :
    [45,48].includes(c)          ? 'linear-gradient(135deg,#546E7A,#607D8B)' :
    t >= 38 ? 'linear-gradient(135deg,#BF360C,#E64A19)' :
    t >= 30 ? 'linear-gradient(135deg,#FF6B00,#F5A623)' :
    t <  15 ? 'linear-gradient(135deg,#283593,#3949AB)' :
              'linear-gradient(135deg,#2E7D32,#43A047)';

  // Umbrella
  const u = umbAdvice(c, rainPct, rainMm);
  document.getElementById('umbIcon').textContent   = u.icon;
  document.getElementById('umbTitle').textContent  = u.title;
  document.getElementById('umbReason').textContent = u.reason;
  document.getElementById('umbCard').style.borderColor = u.color;

  // Food
  const f = foodAdvice(c, tmax, cur.relative_humidity_2m, rainPct);
  document.getElementById('foodIcon').textContent   = f.icon;
  document.getElementById('foodMood').textContent   = f.mood;
  document.getElementById('foodReason').textContent = f.reason;
  const chipsEl = document.getElementById('foodChips');
  chipsEl.innerHTML = '';
  f.chips.forEach(ch => {
    const el = document.createElement('div');
    el.className = 'food-chip'; el.textContent = ch;
    chipsEl.appendChild(el);
  });

  // Hourly (next 24h)
  const hourlyEl = document.getElementById('hourlyStrip');
  hourlyEl.innerHTML = '';
  const nowMs = now.getTime();
  let shown = 0;
  for (let i = 0; i < h.time.length && shown < 24; i++) {
    const t2 = new Date(h.time[i]);
    if (t2 < new Date(nowMs - 3600000)) continue;
    shown++;
    const [,hEmoji] = wmo(h.weather_code[i]);
    const isNow = shown === 1;
    const rp = h.precipitation_probability[i] ?? 0;
    const el = document.createElement('div');
    el.className = 'hour-card' + (isNow ? ' now' : '');
    el.innerHTML = `
      <div class="hour-time">${isNow ? 'Now' : t2.toLocaleTimeString('en-IN',{hour:'2-digit',minute:'2-digit',hour12:true})}</div>
      <div class="hour-icon">${hEmoji}</div>
      <div class="hour-temp">${Math.round(h.temperature_2m[i])}°</div>
      <div class="hour-rain">${rp > 0 ? '💧'+rp+'%' : ''}</div>`;
    hourlyEl.appendChild(el);
  }

  // 10-day
  const fgEl = document.getElementById('forecastGrid');
  fgEl.innerHTML = '';
  const gMin = Math.min(...d.temperature_2m_min);
  const gMax = Math.max(...d.temperature_2m_max);
  const span = gMax - gMin || 1;
  const days = ['Sun','Mon','Tue','Wed','Thu','Fri','Sat'];
  const mons = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];

  for (let i = 0; i < Math.min(10, d.time.length); i++) {
    const dt   = new Date(d.time[i]);
    const fmax = Math.round(d.temperature_2m_max[i]);
    const fmin = Math.round(d.temperature_2m_min[i]);
    const [,fEmoji] = wmo(d.weather_code[i]);
    const fp   = d.precipitation_probability_max[i];
    const fm   = d.precipitation_sum[i];
    const barW = ((fmax - gMin) / span * 100).toFixed(1);
    const dayLabel = i===0 ? 'Today' : i===1 ? 'Tomorrow' : days[dt.getDay()];
    const dayDate  = i <= 1 ? '' : `${dt.getDate()} ${mons[dt.getMonth()]}`;

    const row = document.createElement('div');
    row.className = 'forecast-row' + (i===0 ? ' today-row' : '');
    row.innerHTML = `
      <div><div class="fc-day">${dayLabel}</div><div class="fc-day-sub">${dayDate}</div></div>
      <div class="fc-icon">${fEmoji}</div>
      <div>
        <div class="fc-bar-wrap"><div class="fc-bar" style="width:${barW}%"></div></div>
        <div class="fc-rain-label">${fp}% rain${fm > 0 ? ' · '+fm.toFixed(1)+'mm' : ''}</div>
      </div>
      <div class="fc-temps"><div class="fc-max">${fmax}°</div><div class="fc-min">${fmin}°</div></div>
      <div class="fc-umbrella" style="font-size:20px;text-align:center">${fm>5?'☂️':fm>0?'🌦':'—'}</div>`;
    fgEl.appendChild(row);
  }

  document.getElementById('loading').style.display = 'none';
  document.getElementById('content').style.display = 'block';
}

// ── Fetch via Python proxy ─────────────────────────────────────────────────────
async function loadCity() {
  document.getElementById('loading').style.display = 'flex';
  document.getElementById('content').style.display = 'none';
  document.getElementById('error').style.display   = 'none';

  const val = document.getElementById('citySelect').value;
  const [lat, lon, ...nameParts] = val.split(',');
  const cityName = nameParts.join(',');

  try {
    const res = await fetch(`/weather?lat=${lat}&lon=${lon}`);
    if (!res.ok) {
      const txt = await res.text();
      throw new Error(txt);
    }
    const data = await res.json();
    render(data, cityName);
  } catch(e) {
    document.getElementById('loading').style.display = 'none';
    document.getElementById('error').style.display   = 'block';
    document.getElementById('errMsg').textContent    = 'Error: ' + e.message;
    console.error(e);
  }
}

loadCity();
</script>
</body>
</html>
"""

# ── HTTP Request Handler ───────────────────────────────────────────────────────
class MausamHandler(http.server.BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):
        # Cleaner console output
        print(f"  [{self.command}] {self.path}  →  {args[1] if len(args)>1 else ''}")

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)

        # ── Serve main app ────────────────────────────────────────────────────
        if parsed.path == '/' or parsed.path == '/index.html':
            html = HTML.replace('PORT_PLACEHOLDER', str(PORT))
            self._send(200, 'text/html; charset=utf-8', html.encode())

        # ── Proxy weather API ─────────────────────────────────────────────────
        elif parsed.path == '/weather':
            qs = urllib.parse.parse_qs(parsed.query)
            lat = qs.get('lat', ['28.61'])[0]
            lon = qs.get('lon', ['77.21'])[0]

            api_params = urllib.parse.urlencode({
                'latitude':  lat,
                'longitude': lon,
                'current': ','.join([
                    'temperature_2m', 'apparent_temperature',
                    'relative_humidity_2m', 'weather_code',
                    'wind_speed_10m', 'uv_index', 'precipitation',
                ]),
                'hourly': ','.join([
                    'temperature_2m', 'weather_code',
                    'precipitation_probability', 'precipitation',
                ]),
                'daily': ','.join([
                    'weather_code', 'temperature_2m_max', 'temperature_2m_min',
                    'precipitation_sum', 'precipitation_probability_max', 'uv_index_max',
                ]),
                'timezone':     'Asia/Kolkata',
                'forecast_days': 10,
            })

            url = f'https://api.open-meteo.com/v1/forecast?{api_params}'

            try:
                req = urllib.request.Request(
                    url,
                    headers={'User-Agent': 'MausamApp/1.0 (India Weather)'}
                )
                with urllib.request.urlopen(req, timeout=10) as resp:
                    body = resp.read()
                self._send(200, 'application/json', body)

            except urllib.error.HTTPError as e:
                err = json.dumps({'error': f'Open-Meteo API error: {e.code} {e.reason}'})
                self._send(502, 'application/json', err.encode())

            except urllib.error.URLError as e:
                err = json.dumps({'error': f'Network error: {e.reason}. Check internet connection.'})
                self._send(503, 'application/json', err.encode())

            except Exception as e:
                err = json.dumps({'error': str(e)})
                self._send(500, 'application/json', err.encode())

        else:
            self._send(404, 'text/plain', b'Not found')

    def _send(self, code, ctype, body: bytes):
        self.send_response(code)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-cache')
        self.end_headers()
        self.wfile.write(body)


# ── Main ───────────────────────────────────────────────────────────────────────
def main():
    server = http.server.ThreadingHTTPServer(('localhost', PORT), MausamHandler)

    print()
    print('  ┌─────────────────────────────────────────┐')
    print('  │         🌤  मौसम  India Weather          │')
    print('  ├─────────────────────────────────────────┤')
    print(f'  │   Server : http://localhost:{PORT}        │')
    print('  │   Data   : Open-Meteo (free, no key)    │')
    print('  │   Stop   : Ctrl + C                     │')
    print('  └─────────────────────────────────────────┘')
    print()

    # Open browser after a short delay
    def open_browser():
        import time; time.sleep(0.8)
        webbrowser.open(f'http://localhost:{PORT}')
    threading.Thread(target=open_browser, daemon=True).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\n\n  Stopped. Goodbye! 👋\n')
        server.shutdown()


if __name__ == '__main__':
    main()

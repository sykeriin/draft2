# aerolish_final.py — Complete Working AeroLish with Operational Optimizer
from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
import json
import re
from math import radians, sin, cos, atan2, sqrt
from datetime import datetime

# Load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv not installed, skip

# Optional AI/deterministic summarization imports
try:
    from ai_analysis import WeatherAIAnalyst, tokenize_metar, deterministic_summary
except Exception:  # If ai_analysis is not available or has issues
    WeatherAIAnalyst = None
    tokenize_metar = None
    deterministic_summary = None

# Optional weather APIs import
try:
    from weather_apis import WeatherAPIManager
except Exception:
    WeatherAPIManager = None

app = Flask(__name__)
CORS(app)

# ------------------------------
# Utility: Haversine distance NM
# ------------------------------
def haversine_nm(lat1, lon1, lat2, lon2):
    R_km = 6371.0
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    d = 2 * R_km * atan2(sqrt(a), sqrt(1 - a))
    return d * 0.539957  # km -> NM

# --------------------------------
# Token extractor for risk checks
# --------------------------------
def parse_basic_tokens(raw_metar: str):
    """Extract minimal data points needed for operational decisions from the raw METAR."""
    t = {"vis_sm": None, "ceil_ft": None, "gust": None, "wind": None}
    # Visibility in SM
    m = re.search(r"\b(\d{1,2}(?:\s+\d/\d|\d/\d)?)SM\b", raw_metar)
    if m:
        v = m.group(1).replace(" ", "")
        try:
            if "/" in v:
                num, den = v.split("/")
                t["vis_sm"] = float(num) / float(den)
            else:
                t["vis_sm"] = float(v)
        except Exception:
            pass
    # Ceiling from BKN/OVC base
    m = re.search(r"\b(BKN|OVC)(\d{3})\b", raw_metar)
    if m:
        try:
            t["ceil_ft"] = int(m.group(2)) * 100
        except Exception:
            pass
    # Wind and gusts
    m = re.search(r"\b(\d{3})(\d{2,3})(G(\d{2,3}))?KT\b", raw_metar)
    if m:
        try:
            t["wind"] = (m.group(1), int(m.group(2)))
        except Exception:
            t["wind"] = None
        try:
            t["gust"] = int(m.group(4)) if m.group(4) else None
        except Exception:
            t["gust"] = None
    return t

# ------------------------------------------
# Operational optimizer (alternates, detours)
# ------------------------------------------
def recommend_operational_actions(primary_info, metar_text, severity, all_airports_in_route=None):
    """
    Returns operational decisions for severe or marginal conditions:
    - active: bool
    - reason: short reason for activation
    - risk_alerts: list of strings
    - delay_advisory: optional string
    - alternate_candidates: list of {code,name,severity,distance_nm}
    - detour_suggestions: list of strings
    """
    out = {
        "active": False,
        "reason": "",
        "risk_alerts": [],
        "delay_advisory": None,
        "alternate_candidates": [],
        "detour_suggestions": []
    }
    if not metar_text:
        return out

    tokens = parse_basic_tokens(metar_text)
    # Hard/soft triggers
    hard = (severity == "SEVERE")
    soft = (tokens.get("vis_sm") is not None and tokens["vis_sm"] <= 3.0) or \
           (tokens.get("ceil_ft") is not None and tokens["ceil_ft"] < 1000) or \
           (tokens.get("gust") is not None and tokens["gust"] >= 30)

    if not (hard or soft):
        return out

    out["active"] = True
    out["reason"] = "SEVERE conditions" if hard else "Marginal visibility/ceiling or strong gusts"

    # Risk alerts (concise, fact-based)
    if tokens.get("vis_sm") is not None and tokens["vis_sm"] <= 1.0:
        out["risk_alerts"].append(f"Low visibility {tokens['vis_sm']:.1f}SM — IFR, CAT II/III may be required.")
    if tokens.get("ceil_ft") is not None and tokens["ceil_ft"] < 1000:
        out["risk_alerts"].append(f"Low ceiling {tokens['ceil_ft']} ft — approach minima constraints.")
    if tokens.get("gust") is not None and tokens["gust"] >= 30:
        out["risk_alerts"].append(f"Gusts {tokens['gust']} kt — crosswind/turbulence considerations.")

    # Alternates shortlist using current route context
    if all_airports_in_route and primary_info.get("latitude") and primary_info.get("longitude"):
        lat0, lon0 = primary_info["latitude"], primary_info["longitude"]
        candidates = []
        for ap in all_airports_in_route:
            ap_lat = ap["info"].get("latitude"); ap_lon = ap["info"].get("longitude")
            if not (ap_lat and ap_lon):
                continue
            sev = ap["current_weather"]["parsed"]["severity"]
            if sev == "SEVERE":
                continue
            dist_nm = haversine_nm(lat0, lon0, ap_lat, ap_lon)
            # Bound search radius to ~350 NM
            if dist_nm <= 350:
                candidates.append({
                    "code": ap["code"],
                    "name": ap["info"]["name"],
                    "severity": sev,
                    "distance_nm": round(dist_nm, 1)
                })
        # Prefer CLEAR, then MODERATE, then nearest
        candidates.sort(key=lambda x: (x["severity"] != "CLEAR", x["distance_nm"]))
        out["alternate_candidates"] = candidates[:5]

    # Detour suggestions — bypass severe nodes
    if all_airports_in_route:
        severe_nodes = [ap for ap in all_airports_in_route if ap["current_weather"]["parsed"]["severity"] == "SEVERE"]
        if severe_nodes:
            out["detour_suggestions"].append(
                "Re-sequence to bypass SEVERE airports; plan fuel for extended routing and consider intermediate CLEAR/MODERATE stops."
            )

    # Delay advisory when many legs are degraded
    if all_airports_in_route:
        total = len(all_airports_in_route)
        modsev = sum(1 for ap in all_airports_in_route if ap["current_weather"]["parsed"]["severity"] in ("MODERATE", "SEVERE"))
        if modsev >= max(2, total // 2):
            out["delay_advisory"] = "High disruption risk along the route; consider a ground delay window and monitor AWC convective outlooks/GAIRMETs."

    return out

# -------------------------
# Airport info (OpenFlights)
# -------------------------
def get_airport_info(icao_code):
    """Get airport info from OpenFlights database."""
    icao_code = icao_code.upper().strip()
    try:
        print(f"🔍 Looking up {icao_code}...")
        url = "https://raw.githubusercontent.com/jpatokal/openflights/master/data/airports.dat"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            for line in response.text.split('\n'):
                if line.strip() and '","' in line:
                    try:
                        parts = line.split('","')
                        if len(parts) >= 8:
                            name = parts[1].strip('"')
                            city = parts[2].strip('"')
                            country = parts[3].strip('"')
                            iata = parts[4].strip('"')
                            icao = parts[5].strip('"')
                            lat = parts[6].strip('"')
                            lon = parts[7].strip('"')
                            if (icao.upper() == icao_code or iata.upper() == icao_code) and name != "\\N":
                                try:
                                    latitude = float(lat) if lat != "\\N" else None
                                    longitude = float(lon) if lon != "\\N" else None
                                except Exception:
                                    latitude = longitude = None
                                print(f"✅ Found: {name}, {city}, {country}")
                                return {
                                    'icao': icao.upper() if icao != "\\N" else icao_code,
                                    'iata': iata.upper() if iata != "\\N" else '',
                                    'name': name,
                                    'city': city,
                                    'country': country,
                                    'latitude': latitude,
                                    'longitude': longitude,
                                    'source': 'OpenFlights'
                                }
                    except Exception:
                        continue
    except Exception as e:
        print(f"❌ Airport lookup failed: {e}")

    print(f"⚠️ Using fallback for {icao_code}")
    return {
        'icao': icao_code,
        'iata': '',
        'name': f'Airport {icao_code}',
        'city': 'Unknown',
        'country': 'Unknown',
        'latitude': None,
        'longitude': None,
        'source': 'Fallback'
    }

# -------------------------
# Weather (NOAA -> AWC)
# -------------------------
def get_weather_data(icao):
    """Get weather data with multiple sources."""
    icao = icao.upper()
    # NOAA latest station TXT (line 2) [primary]
    try:
        print(f"🌤️ Getting weather for {icao} from NOAA...")
        url = f"https://tgftp.nws.noaa.gov/data/observations/metar/stations/{icao}.TXT"
        response = requests.get(url, timeout=8)
        if response.status_code == 200:
            lines = response.text.strip().split('\n')
            if len(lines) >= 2:
                metar_line = lines[1].strip()
                if metar_line.startswith(icao):
                    print(f"✅ Got real METAR: {metar_line[:50]}...")
                    return metar_line
    except Exception as e:
        print(f"❌ NOAA failed: {e}")

    # AWC JSON fallback
    try:
        print(f"🌤️ Trying FAA ADDS for {icao}...")
        url = f"https://aviationweather.gov/api/data/metar?format=json&ids={icao}"
        response = requests.get(url, timeout=8)
        if response.status_code == 200:
            data = response.json()
            if isinstance(data, list) and len(data) > 0:
                metar_text = data[0].get('raw_text', '')
                if metar_text:
                    print(f"✅ Got real METAR from FAA: {metar_text[:50]}...")
                    return metar_text
    except Exception as e:
        print(f"❌ FAA ADDS failed: {e}")

    # Synthetic fallback for demos
    print(f"🔄 Using test data for {icao}")
    current_time = datetime.utcnow()
    day = current_time.strftime('%d')
    hour = current_time.strftime('%H')
    minute = current_time.strftime('%M')
    test_data = {
        'KTUS': f'KTUS {day}{hour}{minute}Z 09015G25KT 10SM TS SCT030 BKN060 CB100 28/22 A2992 RMK AO2 TSB45',
        'KLAX': f'KLAX {day}{hour}{minute}Z 25012KT 6SM BR FEW015 SCT250 22/18 A2995 RMK AO2 SLP142',
        'KJFK': f'KJFK {day}{hour}{minute}Z 28015G20KT 8SM BKN020 OVC040 18/15 A3015 RMK AO2 SLP008',
        'KPHX': f'KPHX {day}{hour}{minute}Z 10008KT 10SM CLR 32/05 A2995 RMK AO2 SLP140',
        'VOGO': f'VOGO {day}{hour}{minute}Z 27008KT 3000 -RA SCT015 BKN030 26/24 Q1012 NOSIG',
        'EGLL': f'EGLL {day}{hour}{minute}Z 25015KT 8000 BKN012 OVC020 12/10 Q1018 TEMPO 4000 -RA',
        'RJTT': f'RJTT {day}{hour}{minute}Z 09012KT 9999 FEW030 SCT100 25/19 Q1015 NOSIG'
    }
    return test_data.get(icao, f'{icao} {day}{hour}{minute}Z 27010KT 9999 FEW030 22/18 Q1013')

# -------------------------
# Severity classifier
# -------------------------
def analyze_severity(metar_text):
    """Analyze weather severity."""
    if not metar_text:
        return 'UNKNOWN'
    text = metar_text.upper()
    severe_indicators = ['TS', '+TS', 'TSRA', 'CB', 'FC', '+GR', 'VA', 'SQ']
    if any(indicator in text for indicator in severe_indicators):
        return 'SEVERE'
    moderate_score = 0
    if any(w in text for w in ['RA', '+RA', '-RA', 'SN', '+SN', '-SN', 'DZ', 'SHRA', 'SHSN']):
        moderate_score += 1
    if any(v in text for v in ['BR', 'FG', 'HZ']):
        moderate_score += 1
    if re.search(r'(BKN|OVC)(00\d|01\d|02\d)', text):
        moderate_score += 1
    return 'MODERATE' if moderate_score >= 1 else 'CLEAR'

# -------------------------
# NLP English summary helper
# -------------------------

def get_english_summary(icao: str, metar_text: str) -> str:
    """Return an English summary for the given METAR.
    Prefers AI (DeepSeek/Gemini) if available, falls back to deterministic summary,
    and finally returns raw METAR if parsing fails.
    """
    mt = metar_text or ""
    if not mt:
        return "No METAR available."

    # Try AI first if available and keys likely configured
    if WeatherAIAnalyst is not None:
        try:
            analyst = WeatherAIAnalyst()
            # Only attempt AI if at least one provider key is present
            if analyst.deepseek_api_key or analyst.gemini_api_key:
                text = analyst.summarize_station(icao.upper(), mt)
                if text:
                    return text
        except Exception:
            pass

    # Deterministic fallback using tokenizer if available
    if tokenize_metar is not None and deterministic_summary is not None:
        try:
            tokens = tokenize_metar(mt)
            return deterministic_summary(tokens)
        except Exception:
            pass

    # Last resort: return raw METAR
    return mt

def get_additional_weather_data(icao: str) -> dict:
    """Get TAF, PIREP, SIGMET data for an airport"""
    data = {
        'taf': {'raw_text': '', 'success': False},
        'pirep': {'reports': [], 'count': 0, 'success': False},
        'sigmet': {'reports': [], 'count': 0, 'success': False},
        'airmet': {'reports': [], 'count': 0, 'success': False},
        'winds_aloft': {'altitudes': {}, 'success': False}
    }
    
    # Try to use WeatherAPIManager if available
    if WeatherAPIManager is not None:
        try:
            weather_mgr = WeatherAPIManager()
            
            # Get TAF
            taf_data = weather_mgr.get_taf_data(icao)
            if taf_data.get('success'):
                data['taf'] = {
                    'raw_text': taf_data.get('raw_text', ''),
                    'success': True,
                    'source': taf_data.get('source', 'Unknown')
                }
            
            # Get PIREP
            pirep_data = weather_mgr.get_pirep_data(icao)
            if pirep_data.get('success'):
                data['pirep'] = pirep_data
            
            # Get SIGMET/AIRMET
            sigmet_data = weather_mgr.get_sigmet_airmet_data(icao)
            if sigmet_data.get('success'):
                data['sigmet'] = sigmet_data.get('sigmet', {'reports': [], 'count': 0})
                data['airmet'] = sigmet_data.get('airmet', {'reports': [], 'count': 0})
            
            # Get Winds Aloft
            winds_data = weather_mgr.get_winds_aloft(icao)
            if winds_data.get('success'):
                data['winds_aloft'] = winds_data
                
        except Exception as e:
            print(f"Error getting additional weather data: {e}")
    
    # Fallback test data if no real data available
    if not data['taf']['success'] or not data['taf'].get('raw_text'):
        current_time = datetime.utcnow()
        day = current_time.strftime('%d')
        hour = current_time.strftime('%H')
        next_day = str(int(day) + 1).zfill(2) if int(day) < 31 else "01"
        
        data['taf'] = {
            'raw_text': f'TAF {icao} {day}{hour}00Z {day}{hour}00/{next_day}{hour}00 27010KT 9999 FEW030 TEMPO 27015G25KT 6000 -RA SCT020',
            'success': True,
            'source': 'Test Data'
        }
    
    # Add sample PIREP if none available
    if not data['pirep']['success']:
        data['pirep'] = {
            'reports': [{
                'raw_text': f'{icao} UA /OV {icao}090015/TM 2130/FL080/TP PA28/SK BKN030/WX -RA/TA M05/TB LGT',
                'type': 'PIREP',
                'time': '2130Z'
            }],
            'count': 1,
            'success': True,
            'source': 'Test Data'
        }
    
    # Add sample SIGMET if none available
    if data['sigmet']['count'] == 0:
        data['sigmet'] = {
            'reports': [{
                'raw_text': f'SIGMET ALFA 1 VALID 141200/141600 {icao}- OCCASIONAL SEVERE ICING IN CLOUDS AND PRECIPITATION BETWEEN FL100 AND FL200. CONDS CONTG BYD 1600Z',
                'type': 'SIGMET'
            }],
            'count': 1
        }
    
    # Add sample AIRMET if none available  
    if data['airmet']['count'] == 0:
        data['airmet'] = {
            'reports': [{
                'raw_text': f'AIRMET TANGO UPDT 2 FOR TURBULENCE VALID UNTIL 141800 FROM {icao} TO 100NM RADIUS OCCASIONAL MODERATE TURBULENCE BELOW FL180',
                'type': 'AIRMET'
            }],
            'count': 1
        }
    
    # Add winds aloft if not available
    if not data['winds_aloft']['success']:
        data['winds_aloft'] = {
            'altitudes': {
                '3000': {'wind_dir': 270, 'wind_speed': 15, 'temperature': 10},
                '6000': {'wind_dir': 280, 'wind_speed': 25, 'temperature': 0},
                '9000': {'wind_dir': 290, 'wind_speed': 35, 'temperature': -10},
                '12000': {'wind_dir': 300, 'wind_speed': 45, 'temperature': -20},
                '18000': {'wind_dir': 280, 'wind_speed': 55, 'temperature': -35}
            },
            'success': True,
            'source': 'Test Data'
        }
    
    return data

# -------------------------
# AI briefing (existing)
# -------------------------
def create_ai_briefing(icao, metar_text, severity, airport_info):
    """Create AI weather briefing text blocks."""
    if severity == 'SEVERE':
        summary = f"🚨 SEVERE weather conditions at {icao} ({airport_info['name']}). Thunderstorms and/or other hazardous weather present. Expect significant operational disruptions including delays, diversions, and possible ground stops."
        impact = "Major operational impact expected. Flight delays likely. Ground operations may be suspended. Consider alternate airports and routing."
        recommendations = [
            f"Consider delaying departure to {airport_info['city']} until conditions improve",
            "File multiple alternate airports for contingency planning",
            "Brief flight crew thoroughly on severe weather procedures",
            "Monitor weather radar and updates closely for rapid changes",
            "Coordinate with dispatch for possible route modifications"
        ]
    elif severity == 'MODERATE':
        summary = f"⚠️ MODERATE weather conditions at {icao} ({airport_info['name']}). Weather impacts present that require operational attention and may affect flight operations."
        impact = "Some operational impacts expected. Possible flight delays. Crew briefing recommended. Monitor conditions closely."
        recommendations = [
            f"Monitor weather developments at {airport_info['city']}",
            "Brief flight crew on current weather conditions and trends",
            "Consider additional fuel for possible holding or diversions",
            "Review alternate airport options and brief crew accordingly",
            "Maintain communication with ATC regarding weather conditions"
        ]
    else:
        summary = f"✅ Weather conditions at {icao} ({airport_info['name']}) are favorable for normal flight operations. No significant weather impacts expected."
        impact = "Normal flight operations expected. Standard weather briefing procedures apply. Routine monitoring recommended."
        recommendations = [
            "Standard weather briefing completed - no special procedures required",
            "Normal flight planning and fuel calculations apply",
            "Continue routine weather monitoring during flight planning",
            "Brief crew on standard operating procedures",
            "Weather conditions support normal approach and departure operations"
        ]
    return {
        'executive_summary': summary,
        'operational_impact': impact,
        'recommendations': recommendations
    }

# -------------------------
# Routes
# -------------------------
@app.route('/')
def home():
    return '''
    <!DOCTYPE html>
    <html lang="en">
    <head>
      <meta charset="UTF-8">
      <meta name="viewport" content="width=device-width, initial-scale=1.0">
      <title>AeroLish - Aviation Weather Intelligence</title>
      <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
      <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
      <style>
        :root {
          --bg-dark: #0f172a; --surface-dark: #1e293b; --text-dark: #f1f5f9; --text-muted-dark: #94a3b8;
          --border-dark: #334155; --primary-dark: #22c55e; --accent-dark: #eab308;
          --bg-light: #ffffff; --surface-light: #f8fafc; --text-light: #1e293b;
          --border-light: #e2e8f0; --primary-light: #8b5cf6;
        }
        [data-theme="dark"] { --bg: var(--bg-dark); --surface: var(--surface-dark); --text: var(--text-dark);
          --text-muted: var(--text-muted-dark); --border: var(--border-dark); --primary: var(--primary-dark); --accent: var(--accent-dark); }
        [data-theme="light"] { --bg: var(--bg-light); --surface: var(--surface-light); --text: var(--text-light);
          --text-muted: var(--text-light); --border: var(--border-light); --primary: var(--primary-light); --accent: var(--primary-light); }
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: var(--bg); color: var(--text); line-height: 1.6; transition: all 0.3s ease; }
        .container { max-width: 1400px; margin: 0 auto; padding: 20px; }
        .header { display: flex; justify-content: space-between; align-items: center; padding: 20px 0; border-bottom: 1px solid var(--border); margin-bottom: 30px; }
        .logo { font-size: 28px; font-weight: 700; background: linear-gradient(135deg, var(--primary), var(--accent)); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text; }
        .theme-toggle { background: var(--surface); border: 1px solid var(--border); padding: 10px 16px; border-radius: 10px; cursor: pointer; color: var(--text); transition: all 0.3s ease; }
        .theme-toggle:hover { background: var(--primary); color: white; transform: translateY(-2px); }
        .search-section { background: var(--surface); border: 1px solid var(--border); border-radius: 20px; padding: 28px; margin-bottom: 30px; box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1); }
        .search-row { display: flex; gap: 15px; align-items: center; }
        #airport-input { flex: 1; padding: 16px 20px; border: 2px solid var(--border); border-radius: 15px; background: var(--bg); color: var(--text); font-size: 16px; }
        #airport-input:focus { outline: none; border-color: var(--primary); box-shadow: 0 0 0 4px rgba(34, 197, 94, 0.1); }
        .btn { padding: 16px 28px; border: none; border-radius: 15px; font-weight: 600; cursor: pointer; font-size: 14px; background: linear-gradient(135deg, var(--primary), var(--accent)); color: white; transition: all 0.3s ease; }
        .btn:hover { transform: translateY(-3px); box-shadow: 0 8px 25px rgba(34, 197, 94, 0.4); }
        .main-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 30px; }
        .panel { background: var(--surface); border: 1px solid var(--border); border-radius: 20px; padding: 28px; box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1); }
        .panel-header { font-size: 20px; font-weight: 600; margin-bottom: 24px; padding-bottom: 16px; border-bottom: 1px solid var(--border); }
        #weather-map { width: 100%; height: 400px; border-radius: 16px; border: 1px solid var(--border); }
        .airport-card { background: var(--bg); border: 1px solid var(--border); border-radius: 16px; padding: 20px; margin-bottom: 20px; }
        .airport-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
        .airport-name { font-weight: 600; font-size: 18px; }
        .severity-badge { padding: 6px 16px; border-radius: 25px; font-size: 12px; font-weight: 700; text-transform: uppercase; }
        .severity-CLEAR { background: linear-gradient(135deg, #10b981, #059669); color: white; }
        .severity-MODERATE { background: linear-gradient(135deg, #f59e0b, #d97706); color: white; }
        .severity-SEVERE { background: linear-gradient(135deg, #ef4444, #dc2626); color: white; }
        .severity-UNKNOWN { background: linear-gradient(135deg, #6b7280, #4b5563); color: white; }
        .status-message { padding: 16px 20px; border-radius: 12px; margin-bottom: 20px; font-weight: 500; }
        .status-success { background: linear-gradient(135deg, rgba(34, 197, 94, 0.2), rgba(34, 197, 94, 0.1)); color: #22c55e; border: 1px solid #22c55e; }
        .status-error { background: linear-gradient(135deg, rgba(239, 68, 68, 0.2), rgba(239, 68, 68, 0.1)); color: #ef4444; border: 1px solid #ef4444; }
        @media (max-width: 768px) { .main-grid { grid-template-columns: 1fr; } .search-row { flex-direction: column; } }
      </style>
    </head>
    <body data-theme="dark">
      <div class="container">
        <header class="header">
          <div class="logo">✈️ AeroLish</div>
          <button class="theme-toggle" onclick="toggleTheme()">☀️ Light Mode</button>
        </header>
        <section class="search-section">
          <div class="search-row">
            <input type="text" id="airport-input" placeholder="Enter airport codes (e.g., KTUS or KLAX,KJFK for route)" />
            <button class="btn" onclick="analyzeWeather()">🌤️ Analyze Weather</button>
          </div>
        </section>
        <div id="status-container"></div>
        <div class="main-grid">
          <div class="panel">
            <div class="panel-header">📋 Weather Briefing</div>
            <div id="briefing-content">
              <div style="text-align: center; padding: 60px 20px; color: var(--text-muted);">
                <div style="font-size: 64px; margin-bottom: 20px;">✈️</div>
                <h3>Ready for Weather Analysis</h3>
                <p>Enter airport codes above for comprehensive weather briefings.</p>
                <p style="margin-top: 12px; font-size: 14px;">Try: KTUS, KLAX, KJFK, VOGO, EGLL, RJTT</p>
              </div>
            </div>
          </div>
          <div class="panel">
            <div class="panel-header">🗺️ Interactive Map</div>
            <div id="weather-map"></div>
          </div>
        </div>
      </div>
      <script>
        let map; let markers = [];
        function toggleTheme() {
          const body = document.body;
          const currentTheme = body.getAttribute('data-theme');
          const newTheme = currentTheme === 'light' ? 'dark' : 'light';
          body.setAttribute('data-theme', newTheme);
          const btn = document.querySelector('.theme-toggle');
          btn.textContent = newTheme === 'light' ? '🌙 Dark Mode' : '☀️ Light Mode';
        }
        function initMap() {
          map = L.map('weather-map').setView([39.8, -98.6], 4);
          L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { attribution: '© OpenStreetMap contributors' }).addTo(map);
        }
        function showStatus(message, type = 'success') {
          const container = document.getElementById('status-container');
          container.innerHTML = `<div class="status-message status-${type}">${message}</div>`;
          if (type === 'success') setTimeout(() => container.innerHTML = '', 4000);
        }
        async function analyzeWeather() {
          const input = document.getElementById('airport-input').value.trim();
          if (!input) { showStatus('Please enter airport codes', 'error'); return; }
          const codes = input.split(',').map(c => c.trim().toUpperCase()).filter(c => c);
          try {
            if (codes.length === 1) {
              const response = await fetch(`/api/weather/${codes[0]}`);
              if (!response.ok) throw new Error('Failed to get weather data');
              const data = await response.json();
              displaySingleAirport(data);
              updateMapSingle(data);
              showStatus(`✅ Weather analysis complete for ${codes[0]}`);
            } else {
              const response = await fetch(`/api/route?airports=${codes.join(',')}`);
              if (!response.ok) throw new Error('Failed to analyze route');
              const data = await response.json();
              displayRoute(data);
              updateMapRoute(data);
              showStatus(`✅ Route analysis complete: ${codes.join(' → ')}`);
            }
          } catch (error) {
            showStatus(`❌ Error: ${error.message}`, 'error');
            console.error('Error:', error);
          }
        }
        function displaySingleAirport(data) {
          const content = document.getElementById('briefing-content');
          const airport = data.airport;
          const weather = data.weather;
          const severity = weather.metar.parsed.severity;
          const od = data.operational_decisions || {};
          content.innerHTML = `
            <div class="airport-card">
              <div class="airport-header">
                <div>
                  <div class="airport-name">${data.icao} - ${airport.name}</div>
                  <div style="font-size: 14px; color: var(--text-muted); margin-top: 4px;">
                    ${airport.city}, ${airport.country}
                  </div>
                </div>
                <div class="severity-badge severity-${severity}">${severity}</div>
              </div>
              <div style="margin-top: 16px; color: var(--text-muted);"><strong>Current conditions:</strong> ${weather.metar.english_summary || weather.metar.raw_text}</div>
              <div style="margin-top: 16px; padding: 16px; background: var(--surface); border-radius: 12px;">
                <h4 style="color: var(--primary); margin-bottom: 8px;">🤖 AI Analysis</h4>
                <p style="margin-bottom: 12px;"><strong>Summary:</strong> ${data.ai_briefing.executive_summary}</p>
                <p style="margin-bottom: 12px;"><strong>Impact:</strong> ${data.ai_briefing.operational_impact}</p>
                <div><strong>Recommendations:</strong>
                  <ul style="margin-left: 20px; margin-top: 8px;">
                    ${data.ai_briefing.recommendations.map(rec => `<li>${rec}</li>`).join('')}
                  </ul>
                </div>
              </div>
            </div>
            ${od.active ? `
              <div class="airport-card" style="border-left: 6px solid #dc2626;">
                <div class="airport-header">
                  <div class="airport-name">⚡ Operational Decisions</div>
                  <span class="severity-badge severity-SEVERE">${od.reason}</span>
                </div>
                ${od.risk_alerts && od.risk_alerts.length ? `<ul>${od.risk_alerts.map(x=>`<li>${x}</li>`).join('')}</ul>` : ''}
                ${od.delay_advisory ? `<div class="status-message status-error">${od.delay_advisory}</div>` : ''}
                ${od.alternate_candidates && od.alternate_candidates.length ? `<div><strong>Alternates:</strong> ${od.alternate_candidates.map(a=>`${a.code} (${a.distance_nm} NM, ${a.severity})`).join(' · ')}</div>` : ''}
                ${od.detour_suggestions && od.detour_suggestions.length ? `<div style="margin-top:8px;">${od.detour_suggestions.join('<br>')}</div>` : ''}
              </div>` : ''}
          `;
        }
        function displayRoute(data) {
          const content = document.getElementById('briefing-content');
          const od = data.operational_decisions || {};
          let html = `
            <div style="margin-bottom: 24px;">
              <h3>Route: ${data.route.airports.join(' → ')}</h3>
              <div class="severity-badge severity-${data.overall_conditions}" style="margin-top: 8px;">Overall: ${data.overall_conditions}</div>
            </div>
          `;
          data.analysis.airports.forEach(airport => {
            const severity = airport.current_weather.parsed.severity;
            html += `
              <div class="airport-card">
                <div class="airport-header">
                  <div>
                    <div class="airport-name">${airport.code} - ${airport.info.name}</div>
                    <div style="font-size: 14px; color: var(--text-muted);">${airport.info.city}, ${airport.info.country}</div>
                  </div>
                  <div class="severity-badge severity-${severity}">${severity}</div>
                </div>
                <div style="margin-top: 12px; color: var(--text-muted);">${airport.current_weather.english_summary || airport.current_weather.raw_text}</div>
              </div>
            `;
          });
          if (od.active) {
            html += `
              <div class="airport-card" style="border-left: 6px solid #dc2626;">
                <div class="airport-header">
                  <div class="airport-name">⚡ Operational Decisions (Route)</div>
                  <span class="severity-badge severity-SEVERE">${od.reason}</span>
                </div>
                ${od.risk_alerts && od.risk_alerts.length ? `<ul>${od.risk_alerts.map(x=>`<li>${x}</li>`).join('')}</ul>` : ''}
                ${od.delay_advisory ? `<div class="status-message status-error">${od.delay_advisory}</div>` : ''}
                ${od.alternate_candidates && od.alternate_candidates.length ? `<div><strong>Alternates near departure:</strong> ${od.alternate_candidates.map(a=>`${a.code} (${a.distance_nm} NM, ${a.severity})`).join(' · ')}</div>` : ''}
                ${od.detour_suggestions && od.detour_suggestions.length ? `<div style="margin-top:8px;">${od.detour_suggestions.join('<br>')}</div>` : ''}
              </div>
            `;
          }
          content.innerHTML = html;
        }
        function clearMap(){ markers.forEach(m => map.removeLayer(m)); markers = []; }
        function updateMapSingle(data) {
          clearMap();
          const airport = data.airport;
          if (airport.latitude && airport.longitude) {
            const severity = data.weather.metar.parsed.severity;
            const colors = {'SEVERE': '#ef4444', 'MODERATE': '#f59e0b', 'CLEAR': '#22c55e', 'UNKNOWN': '#64748b'};
            const marker = L.circleMarker([airport.latitude, airport.longitude], { radius: 15, fillColor: colors[severity], color: '#ffffff', weight: 3, opacity: 1, fillOpacity: 0.8 }).addTo(map);
            marker.bindPopup(`<strong>${data.icao} - ${airport.name}</strong><br><span style="color: ${colors[severity]}; font-weight: bold;">${severity}</span><br>${airport.city}, ${airport.country}`);
            markers.push(marker);
            map.setView([airport.latitude, airport.longitude], 8);
          }
        }
        function updateMapRoute(data) {
          clearMap();
          const validPoints = data.timeline.filter(p => p.latitude && p.longitude);
          if (validPoints.length === 0) return;
          const colors = {'SEVERE': '#ef4444', 'MODERATE': '#f59e0b', 'CLEAR': '#22c55e', 'UNKNOWN': '#64748b'};
          validPoints.forEach((point, index) => {
            const marker = L.circleMarker([point.latitude, point.longitude], { radius: 12, fillColor: colors[point.severity], color: '#ffffff', weight: 2, opacity: 1, fillOpacity: 0.8 }).addTo(map);
            const position = index === 0 ? '🛫 Departure' : index === validPoints.length - 1 ? '🛬 Arrival' : '📍 Waypoint';
            marker.bindPopup(`<strong>${point.icao} - ${point.name}</strong><br><span style="color: ${colors[point.severity]}; font-weight: bold;">${point.severity}</span><br>${position}`);
            markers.push(marker);
          });
          if (validPoints.length > 1) {
            const coords = validPoints.map(p => [p.latitude, p.longitude]);
            const worstSeverity = validPoints.map(p => p.severity).includes('SEVERE') ? 'SEVERE' :
                                  validPoints.map(p => p.severity).includes('MODERATE') ? 'MODERATE' : 'CLEAR';
            L.polyline(coords, { color: colors[worstSeverity], weight: 4, opacity: 0.7 }).addTo(map);
            map.fitBounds(coords, { padding: [20, 20] });
          }
        }
        document.getElementById('airport-input').addEventListener('keypress', function(e){ if (e.key === 'Enter') analyzeWeather(); });
        document.addEventListener('DOMContentLoaded', initMap);
      </script>
    </body>
    </html>
    '''

# -------------------------
# API: Single station
# -------------------------
@app.route('/api/weather/<icao>')
def get_weather(icao):
    try:
        print(f"\n🎯 Weather request for {icao}")
        airport_info = get_airport_info(icao)
        metar_text = get_weather_data(icao)
        severity = analyze_severity(metar_text)
        ai_briefing = create_ai_briefing(icao, metar_text, severity, airport_info)
        
        # Get additional weather data (TAF, PIREP, SIGMET, etc.)
        additional_data = get_additional_weather_data(icao)

        # Operational optimizer for this airport (no route context here)
        operational_decisions = recommend_operational_actions(airport_info, metar_text, severity, None)

        response = {
            'icao': icao.upper(),
            'airport': airport_info,
            'weather': {
                'metar': {
                    'raw_text': metar_text,
                    'parsed': {'severity': severity},
                    'english_summary': get_english_summary(icao, metar_text)
                },
                'taf': additional_data['taf'],
                'pirep': additional_data['pirep'],
                'sigmet': additional_data['sigmet'],
                'airmet': additional_data['airmet'],
                'winds_aloft': additional_data['winds_aloft']
            },
            'ai_briefing': ai_briefing,
            'operational_decisions': operational_decisions,
            'timestamp': datetime.utcnow().isoformat()
        }
        print(f"✅ Success: {severity} conditions at {airport_info['name']}")
        return jsonify(response)
    except Exception as e:
        print(f"❌ Error: {e}")
        return jsonify({'error': str(e)}), 500

# -------------------------
# API: Route analysis
# -------------------------
@app.route('/api/route')
def analyze_route():
    try:
        airports_param = request.args.get('airports', '')
        codes = [code.strip().upper() for code in airports_param.split(',') if code.strip()]
        if len(codes) < 2:
            return jsonify({'error': 'Need at least 2 airports'}), 400

        print(f"\n🛫 Route: {' → '.join(codes)}")
        airports_data = []
        timeline = []
        severities = []

        for code in codes:
            airport_info = get_airport_info(code)
            metar_text = get_weather_data(code)
            severity = analyze_severity(metar_text)
            severities.append(severity)

            airports_data.append({
                'code': code,
                'info': airport_info,
                'current_weather': {
                    'raw_text': metar_text,
                    'parsed': {'severity': severity},
                    'english_summary': get_english_summary(code, metar_text)
                }
            })

            timeline.append({
                'icao': code,
                'name': airport_info['name'],
                'latitude': airport_info['latitude'],
                'longitude': airport_info['longitude'],
                'severity': severity
            })

            print(f"📍 {code}: {airport_info['name']}")

        overall = 'SEVERE' if 'SEVERE' in severities else 'MODERATE' if 'MODERATE' in severities else 'CLEAR'

        # Operational optimizer with full route context; use departure airport as reference
        dep_info = airports_data[0]['info']
        dep_metar = airports_data[0]['current_weather']['raw_text']
        dep_sev = airports_data[0]['current_weather']['parsed']['severity']
        operational_decisions = recommend_operational_actions(dep_info, dep_metar, dep_sev, airports_data)

        response = {
            'route': {'airports': codes},
            'analysis': {'airports': airports_data},
            'timeline': timeline,
            'overall_conditions': overall,
            'operational_decisions': operational_decisions,
            'timestamp': datetime.utcnow().isoformat()
        }

        print(f"✅ Route complete: {overall}")
        return jsonify(response)
    except Exception as e:
        print(f"❌ Route error: {e}")
        return jsonify({'error': str(e)}), 500

# -------------------------
# Entrypoint
# -------------------------
if __name__ == '__main__':
    print("🛫 AeroLish - Complete Aviation Weather System")
    print("📡 Server: http://localhost:5000")
    print("🌍 Airports: Real data from OpenFlights database")
    print("🌤️ Weather: NOAA → FAA ADDS → Test data fallbacks")
    print("🤖 AI: Comprehensive operational briefings + Optimizer")
    print("🗺️ Map: Interactive with route visualization")
    print("✅ Ready to analyze weather worldwide!")
    print("=" * 60)
    app.run(host='0.0.0.0', port=5000, debug=True)

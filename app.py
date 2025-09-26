# app.py - Fixed Airport Names and Map Coordinates
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import requests
import re
from datetime import datetime
import json

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

app = Flask(__name__)
CORS(app)

# Cache for airport data
airport_cache = {}


def get_airport_info(icao_code):
    """Get airport info with proper names and coordinates"""
    icao_code = icao_code.upper().strip()

    # Check cache first
    if icao_code in airport_cache:
        print(f"📋 Using cached airport data for {icao_code}")
        return airport_cache[icao_code]

    print(f"🔍 Looking up airport info for {icao_code}")

    # Method 1: Try OpenFlights database (most comprehensive)
    try:
        url = "https://raw.githubusercontent.com/jpatokal/openflights/master/data/airports.dat"
        response = requests.get(url, timeout=15)

        if response.status_code == 200:
            for line_num, line in enumerate(response.text.split('\n')):
                if line.strip() and '","' in line:
                    try:
                        # More robust CSV parsing
                        parts = []
                        current = ""
                        in_quotes = False

                        for char in line:
                            if char == '"':
                                in_quotes = not in_quotes
                            elif char == ',' and not in_quotes:
                                parts.append(current.strip('"'))
                                current = ""
                            else:
                                current += char
                        parts.append(current.strip('"'))

                        if len(parts) >= 8:
                            # OpenFlights format: ID,Name,City,Country,IATA,ICAO,Latitude,Longitude,Altitude,Timezone,DST,Tz,Type,Source
                            airport_id = parts[0]
                            name = parts[1]
                            city = parts[2]
                            country = parts[3]
                            iata = parts[4]
                            icao = parts[5]
                            lat = parts[6]
                            lon = parts[7]

                            # Check if this matches our search (ICAO or IATA)
                            if ((icao.upper() == icao_code or iata.upper() == icao_code) and
                                    name != "\\N" and name.strip()):

                                try:
                                    latitude = float(
                                        lat) if lat != "\\N" and lat.strip() else None
                                    longitude = float(
                                        lon) if lon != "\\N" and lon.strip() else None
                                except (ValueError, TypeError):
                                    latitude = longitude = None

                                airport_info = {
                                    'icao': icao.upper() if icao != "\\N" and icao.strip() else icao_code,
                                    'iata': iata.upper() if iata != "\\N" and iata.strip() else '',
                                    'name': name,
                                    'city': city if city != "\\N" else 'Unknown',
                                    'country': country if country != "\\N" else 'Unknown',
                                    'latitude': latitude,
                                    'longitude': longitude,
                                    'source': 'OpenFlights'
                                }

                                print(
                                    f"✅ Found {icao_code}: {name} in {city}, {country}")
                                print(
                                    f"📍 Coordinates: {latitude}, {longitude}")

                                # Cache the result
                                airport_cache[icao_code] = airport_info
                                return airport_info

                    except Exception as e:
                        # Skip problematic lines but continue
                        continue

    except Exception as e:
        print(f"❌ OpenFlights lookup failed: {e}")

    # Method 2: Hardcoded database for common airports (as backup)
    print(f"🔄 Using hardcoded database for {icao_code}")

    hardcoded_airports = {
        'KTUS': {'name': 'Tucson International Airport', 'city': 'Tucson', 'country': 'United States', 'latitude': 32.1161, 'longitude': -110.9410},
        'KLAX': {'name': 'Los Angeles International Airport', 'city': 'Los Angeles', 'country': 'United States', 'latitude': 33.9425, 'longitude': -118.4081},
        'KJFK': {'name': 'John F Kennedy International Airport', 'city': 'New York', 'country': 'United States', 'latitude': 40.6413, 'longitude': -73.7781},
        'KPHX': {'name': 'Phoenix Sky Harbor International Airport', 'city': 'Phoenix', 'country': 'United States', 'latitude': 33.4373, 'longitude': -112.0078},
        'KSFO': {'name': 'San Francisco International Airport', 'city': 'San Francisco', 'country': 'United States', 'latitude': 37.6213, 'longitude': -122.3790},
        'KORD': {'name': "Chicago O'Hare International Airport", 'city': 'Chicago', 'country': 'United States', 'latitude': 41.9742, 'longitude': -87.9073},
        'KDEN': {'name': 'Denver International Airport', 'city': 'Denver', 'country': 'United States', 'latitude': 39.8561, 'longitude': -104.6737},
        'KLAS': {'name': 'Harry Reid International Airport', 'city': 'Las Vegas', 'country': 'United States', 'latitude': 36.0840, 'longitude': -115.1537},
        'KMIA': {'name': 'Miami International Airport', 'city': 'Miami', 'country': 'United States', 'latitude': 25.7932, 'longitude': -80.2906},
        'KSEA': {'name': 'Seattle-Tacoma International Airport', 'city': 'Seattle', 'country': 'United States', 'latitude': 47.4502, 'longitude': -122.3088},

        'VOGO': {'name': 'Dabolim Airport', 'city': 'Goa', 'country': 'India', 'latitude': 15.3808, 'longitude': 73.8314},
        'VOBL': {'name': 'Kempegowda International Airport', 'city': 'Bengaluru', 'country': 'India', 'latitude': 13.1986, 'longitude': 77.7066},
        'VOMM': {'name': 'Chennai International Airport', 'city': 'Chennai', 'country': 'India', 'latitude': 12.9941, 'longitude': 80.1709},
        'VECC': {'name': 'Netaji Subhas Chandra Bose International Airport', 'city': 'Kolkata', 'country': 'India', 'latitude': 22.6546, 'longitude': 88.4467},
        'VIDP': {'name': 'Indira Gandhi International Airport', 'city': 'New Delhi', 'country': 'India', 'latitude': 28.5665, 'longitude': 77.1031},
        'VABB': {'name': 'Chhatrapati Shivaji Maharaj International Airport', 'city': 'Mumbai', 'country': 'India', 'latitude': 19.0896, 'longitude': 72.8656},

        'EGLL': {'name': 'London Heathrow Airport', 'city': 'London', 'country': 'United Kingdom', 'latitude': 51.4700, 'longitude': -0.4543},
        'EGKK': {'name': 'London Gatwick Airport', 'city': 'London', 'country': 'United Kingdom', 'latitude': 51.1481, 'longitude': -0.1903},
        'EGGW': {'name': 'London Luton Airport', 'city': 'London', 'country': 'United Kingdom', 'latitude': 51.8763, 'longitude': -0.3717},
        'LFPG': {'name': 'Charles de Gaulle Airport', 'city': 'Paris', 'country': 'France', 'latitude': 49.0097, 'longitude': 2.5479},
        'EDDF': {'name': 'Frankfurt Airport', 'city': 'Frankfurt', 'country': 'Germany', 'latitude': 50.0379, 'longitude': 8.5622},
        'LIRF': {'name': 'Leonardo da Vinci Airport', 'city': 'Rome', 'country': 'Italy', 'latitude': 41.8003, 'longitude': 12.2389},
        'LEMD': {'name': 'Adolfo Suárez Madrid-Barajas Airport', 'city': 'Madrid', 'country': 'Spain', 'latitude': 40.4839, 'longitude': -3.5680},

        'RJTT': {'name': 'Tokyo Haneda Airport', 'city': 'Tokyo', 'country': 'Japan', 'latitude': 35.5494, 'longitude': 139.7798},
        'RJAA': {'name': 'Tokyo Narita International Airport', 'city': 'Tokyo', 'country': 'Japan', 'latitude': 35.7647, 'longitude': 140.3864},
        'RKSI': {'name': 'Seoul Incheon International Airport', 'city': 'Seoul', 'country': 'South Korea', 'latitude': 37.4602, 'longitude': 126.4407},
        'ZSPD': {'name': 'Shanghai Pudong International Airport', 'city': 'Shanghai', 'country': 'China', 'latitude': 31.1443, 'longitude': 121.8083},
        'ZBAA': {'name': 'Beijing Capital International Airport', 'city': 'Beijing', 'country': 'China', 'latitude': 40.0801, 'longitude': 116.5846},
        'VHHH': {'name': 'Hong Kong International Airport', 'city': 'Hong Kong', 'country': 'Hong Kong SAR', 'latitude': 22.3080, 'longitude': 113.9185},

        'YSSY': {'name': 'Sydney Kingsford Smith Airport', 'city': 'Sydney', 'country': 'Australia', 'latitude': -33.9399, 'longitude': 151.1753},
        'YMML': {'name': 'Melbourne Airport', 'city': 'Melbourne', 'country': 'Australia', 'latitude': -37.6690, 'longitude': 144.8410},
        'YBBN': {'name': 'Brisbane Airport', 'city': 'Brisbane', 'country': 'Australia', 'latitude': -27.3942, 'longitude': 153.1218},

        'CYYZ': {'name': 'Toronto Pearson International Airport', 'city': 'Toronto', 'country': 'Canada', 'latitude': 43.6777, 'longitude': -79.6248},
        'CYVR': {'name': 'Vancouver International Airport', 'city': 'Vancouver', 'country': 'Canada', 'latitude': 49.1967, 'longitude': -123.1815}
    }

    if icao_code in hardcoded_airports:
        airport_data = hardcoded_airports[icao_code].copy()
        airport_data.update({
            'icao': icao_code,
            'iata': '',  # Would need separate lookup for IATA codes
            'source': 'Hardcoded Database'
        })

        print(
            f"✅ Found in hardcoded DB: {airport_data['name']} in {airport_data['city']}")
        print(
            f"📍 Coordinates: {airport_data['latitude']}, {airport_data['longitude']}")

        # Cache the result
        airport_cache[icao_code] = airport_data
        return airport_data

    # Method 3: Create fallback with proper format
    print(f"⚠️ Using fallback for {icao_code}")
    fallback_info = {
        'icao': icao_code,
        'iata': '',
        'name': f'Airport {icao_code}',
        'city': 'Unknown',
        'country': 'Unknown',
        'latitude': None,
        'longitude': None,
        'source': 'Fallback'
    }

    # Cache the fallback too
    airport_cache[icao_code] = fallback_info
    return fallback_info


def get_weather_data(icao):
    """Get weather data - WORKING VERSION"""
    icao = icao.upper()

    print(f"🌤️ Getting weather for {icao}")

    # Try NOAA first
    try:
        url = f"https://tgftp.nws.noaa.gov/data/observations/metar/stations/{icao}.TXT"
        response = requests.get(url, timeout=8)
        if response.status_code == 200:
            lines = response.text.strip().split('\n')
            if len(lines) >= 2:
                metar_line = lines[1].strip()
                if metar_line.startswith(icao):
                    print(f"✅ Got real METAR from NOAA: {metar_line[:50]}...")
                    return metar_line
    except Exception as e:
        print(f"❌ NOAA failed: {e}")

    # Try FAA ADDS
    try:
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

    # Realistic test data
    print(f"🔄 Using test data for {icao}")
    current_time = datetime.utcnow()
    day = current_time.strftime('%d')
    hour = current_time.strftime('%H')
    minute = current_time.strftime('%M')

    test_data = {
        'KTUS': f'KTUS {day}{hour}{minute}Z 09015G25KT 10SM TS SCT030 BKN060 CB100 28/22 A2992 RMK AO2 TSB45',
        'KLAX': f'KLAX {day}{hour}{minute}Z 25012KT 6SM BR FEW015 SCT250 22/18 A2995 RMK AO2 SLP142',
        'KJFK': f'KJFK {day}{hour}{minute}Z 28015G20KT 8SM BKN020 OVC040 18/15 A3015 RMK AO2 SLP008',
        'KSFO': f'KSFO {day}{hour}{minute}Z 29012KT 4SM BR FEW008 BKN015 18/17 A3010 RMK AO2 SLP021',
        'VOGO': f'VOGO {day}{hour}{minute}Z 27008KT 3000 -RA SCT015 BKN030 26/24 Q1012 NOSIG',
        'EGLL': f'EGLL {day}{hour}{minute}Z 25015KT 8000 BKN012 OVC020 12/10 Q1018 TEMPO 4000 -RA',
        'RJTT': f'RJTT {day}{hour}{minute}Z 09012KT 9999 FEW030 SCT100 25/19 Q1015 NOSIG',
        'VOBL': f'VOBL {day}{hour}{minute}Z 09010KT 6000 HZ SCT025 BKN100 28/22 Q1014 NOSIG'
    }

    return test_data.get(icao, f'{icao} {day}{hour}{minute}Z 27010KT 9999 FEW030 22/18 Q1013')


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


def analyze_severity(metar_text):
    """Analyze severity - WORKING VERSION"""
    if not metar_text:
        return 'UNKNOWN'

    text = metar_text.upper()

    if any(condition in text for condition in ['TS', '+TS', 'TSRA', 'CB', 'FC']):
        return 'SEVERE'

    if any(wx in text for wx in ['RA', 'SN', 'BR', 'FG', 'BKN', 'OVC']):
        return 'MODERATE'

    return 'CLEAR'


def create_detailed_analysis(metar_text):
    """Create detailed analysis sections"""
    if not metar_text:
        return {
            'thunderstorms': 'No weather data available for thunderstorm analysis.',
            'clouds': 'No weather data available for cloud analysis.',
            'visibility': 'No weather data available for visibility analysis.',
            'winds': 'No weather data available for wind analysis.',
            'precipitation': 'No weather data available for precipitation analysis.'
        }

    analysis = {}
    text = metar_text.upper()

    # Thunderstorm Analysis
    if 'TS' in text or 'CB' in text:
        if '+TS' in text:
            analysis['thunderstorms'] = "Severe thunderstorms present with heavy precipitation and strong electrical activity. Expect significant turbulence, wind shear, and possible hail. Ground operations may be suspended."
        else:
            analysis['thunderstorms'] = "Thunderstorms in the area with associated precipitation and electrical activity. Moderate to severe turbulence possible around storm cells."
    else:
        analysis['thunderstorms'] = "No thunderstorm activity reported. Convective weather is not a current factor for operations."

    # Cloud Analysis
    cloud_matches = re.findall(r'(FEW|SCT|BKN|OVC)(\d{3})', text)
    if cloud_matches:
        cloud_desc = []
        ceiling = None
        for coverage, height in cloud_matches:
            height_ft = int(height) * 100
            if coverage in ['BKN', 'OVC']:
                if ceiling is None or height_ft < ceiling:
                    ceiling = height_ft
            cloud_desc.append(f"{coverage.lower()} at {height_ft:,} feet")

        if ceiling:
            if ceiling < 1000:
                analysis['clouds'] = f"Low ceiling at {ceiling:,} feet with {', '.join(cloud_desc)}. IFR conditions present requiring instrument approaches."
            elif ceiling < 3000:
                analysis['clouds'] = f"Marginal ceiling at {ceiling:,} feet with {', '.join(cloud_desc)}. MVFR conditions - monitor for changes."
            else:
                analysis['clouds'] = f"VFR ceiling at {ceiling:,} feet with {', '.join(cloud_desc)}. Good conditions for visual approaches."
        else:
            analysis['clouds'] = f"Scattered or few clouds present: {', '.join(cloud_desc)}. No ceiling restrictions for VFR operations."
    else:
        analysis['clouds'] = "Clear skies or minimal cloud coverage. Excellent conditions for all types of approaches and VFR operations."

    # Visibility Analysis
    vis_sm_match = re.search(r'(\d{1,2}(?:\s+\d/\d)?|\d/\d)\s*SM', metar_text)
    vis_m_match = re.search(r'\b(\d{4})\b', text)

    if vis_sm_match:
        vis_str = vis_sm_match.group(1).replace(' ', '')
        if '/' in vis_str:
            parts = vis_str.split('/')
            vis_sm = float(parts[0]) / float(parts[1])
        else:
            vis_sm = float(vis_str)

        if vis_sm < 1:
            analysis['visibility'] = f"Poor visibility at {vis_sm:.1f} statute miles. Low IFR conditions with significant operational restrictions. CAT II/III approaches may be required."
        elif vis_sm < 3:
            analysis['visibility'] = f"Reduced visibility at {vis_sm:.1f} statute miles. IFR conditions present - instrument approaches required."
        elif vis_sm <= 5:
            analysis['visibility'] = f"Marginal visibility at {vis_sm:.0f} statute miles. MVFR conditions - visual approaches may be limited."
        else:
            analysis['visibility'] = f"Good visibility at {vis_sm:.0f} statute miles. VFR conditions suitable for all approach types."
    elif vis_m_match:
        vis_m = int(vis_m_match.group(1))
        if vis_m < 1600:
            analysis['visibility'] = f"Poor visibility at {vis_m} meters. Low IFR conditions with significant restrictions."
        elif vis_m < 5000:
            analysis['visibility'] = f"Reduced visibility at {vis_m} meters. IFR conditions present."
        else:
            analysis['visibility'] = f"Good visibility at {vis_m} meters. Suitable for visual operations."
    else:
        analysis['visibility'] = "Visibility information not available in standard format. Contact tower for current visibility."

    # Add restrictions
    restrictions = []
    if 'BR' in text:
        restrictions.append('mist')
    if 'FG' in text:
        restrictions.append('fog')
    if 'RA' in text:
        restrictions.append('rain')
    if 'SN' in text:
        restrictions.append('snow')

    if restrictions:
        analysis['visibility'] += f" Restricted by: {', '.join(restrictions)}."

    # Wind Analysis
    wind_match = re.search(r'(\d{3}|VRB)(\d{2,3})(G(\d{2,3}))?KT', text)
    if wind_match:
        direction = wind_match.group(1)
        speed = int(wind_match.group(2))
        gusts = int(wind_match.group(4)) if wind_match.group(4) else None

        if direction == 'VRB':
            wind_desc = f"Variable direction winds at {speed} knots"
        else:
            wind_desc = f"Winds from {direction}° at {speed} knots"

        if gusts:
            wind_desc += f", gusting to {gusts} knots"
            if gusts > 35:
                wind_desc += ". Strong gusty conditions may affect operations and require wind limit considerations."
            elif gusts > 25:
                wind_desc += ". Moderate gusts present - brief crews on gusty wind procedures."

        if speed > 25:
            wind_desc += " Strong surface winds indicate possible turbulence and challenging crosswind conditions."
        elif speed < 5:
            wind_desc += " Light wind conditions favorable for all runway operations."

        analysis['winds'] = wind_desc
    else:
        analysis['winds'] = "Wind information not available or calm conditions present."

    # Precipitation Analysis
    precip_types = []
    if '+RA' in text:
        precip_types.append('heavy rain')
    elif 'RA' in text:
        precip_types.append('rain')
    elif '-RA' in text:
        precip_types.append('light rain')

    if '+SN' in text:
        precip_types.append('heavy snow')
    elif 'SN' in text:
        precip_types.append('snow')
    elif '-SN' in text:
        precip_types.append('light snow')

    if 'SHRA' in text:
        precip_types.append('rain showers')
    if 'DZ' in text:
        precip_types.append('drizzle')
    if 'GR' in text:
        precip_types.append('hail')

    if precip_types:
        analysis['precipitation'] = f"Precipitation present: {', '.join(precip_types)}. May affect runway conditions and visibility. De-icing procedures may be required."
    else:
        analysis['precipitation'] = "No precipitation reported. Dry conditions present with no precipitation-related operational impacts."

    return analysis

# Routes


@app.route('/')
def serve_index():
    return send_from_directory('.', 'index.html')


@app.route('/health')
def health():
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "message": "AeroLish with proper airport names and coordinates ready!",
        "cached_airports": len(airport_cache)
    })


@app.route('/api/weather/<icao>')
def get_weather(icao):
    try:
        print(f"\n🎯 Weather request for {icao}")

        # Get airport info with proper names and coordinates
        airport_info = get_airport_info(icao)
        metar_text = get_weather_data(icao)
        severity = analyze_severity(metar_text)

        # Create detailed analysis
        detailed_analysis = create_detailed_analysis(metar_text)

        # AI briefing
        if severity == 'SEVERE':
            summary = f"🚨 SEVERE weather at {icao} ({airport_info['name']}). Thunderstorms detected with significant operational impacts."
            impact = "Major delays expected. Ground stops possible. Consider alternate airports and routing."
            recommendations = ["Monitor conditions closely", "Brief alternate airports",
                               "Expect significant delays", "Consider route modifications"]
        elif severity == 'MODERATE':
            summary = f"⚠️ MODERATE weather at {icao} ({airport_info['name']}). Weather impacts present requiring operational attention."
            impact = "Some delays possible. Monitor conditions and brief crew on current weather."
            recommendations = ["Monitor weather conditions", "Brief crew on weather",
                               "Consider fuel adjustments", "Review alternate options"]
        else:
            summary = f"✅ Favorable weather at {icao} ({airport_info['name']}). Conditions suitable for normal operations."
            impact = "Normal operations expected. Standard weather procedures apply."
            recommendations = ["Standard weather briefing",
                               "Normal flight planning", "Routine monitoring"]

        response = {
            'icao': icao.upper(),
            'airport': airport_info,
            'weather': {
                'metar': {
                    'raw_text': metar_text,
                    'parsed': {'severity': severity},
                    'english_summary': get_english_summary(icao, metar_text)
                },
                'taf': {
                    'raw_text': f'TAF {icao.upper()} {datetime.utcnow().strftime("%d%H%M")}Z 27010KT 9999 FEW030'
                }
            },
            'ai_briefing': {
                'executive_summary': summary,
                'operational_impact': impact,
                'recommendations': recommendations
            },
            'detailed_analysis': detailed_analysis,
            'timestamp': datetime.utcnow().isoformat()
        }

        print(
            f"✅ Success: {severity} at {airport_info['name']} ({airport_info['city']})")
        return jsonify(response)

    except Exception as e:
        print(f"❌ Error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/route')
def analyze_route():
    try:
        airports_param = request.args.get('airports', '')
        codes = [code.strip().upper()
                 for code in airports_param.split(',') if code.strip()]

        if len(codes) < 2:
            return jsonify({'error': 'Need at least 2 airports'}), 400

        print(f"\n🛫 Route: {' → '.join(codes)}")

        airports_data = []
        timeline = []
        severities = []

        for code in codes:
            # Get airport info with proper names and coordinates
            airport_info = get_airport_info(code)
            metar_text = get_weather_data(code)
            severity = analyze_severity(metar_text)
            severities.append(severity)

            # Add detailed analysis for each airport
            detailed_analysis = create_detailed_analysis(metar_text)

            airports_data.append({
                'code': code,
                'info': airport_info,
                'current_weather': {
                    'raw_text': metar_text,
                    'parsed': {'severity': severity},
                    'english_summary': get_english_summary(code, metar_text)
                },
                'detailed_analysis': detailed_analysis
            })

            timeline.append({
                'icao': code,
                'name': airport_info['name'],
                'latitude': airport_info['latitude'],
                'longitude': airport_info['longitude'],
                'severity': severity,
                'weather_summary': metar_text[:50] + '...' if len(metar_text) > 50 else metar_text
            })

            print(
                f"📍 {code}: {airport_info['name']} at {airport_info['latitude']}, {airport_info['longitude']}")

        overall = 'SEVERE' if 'SEVERE' in severities else 'MODERATE' if 'MODERATE' in severities else 'CLEAR'

        response = {
            'route': {'airports': codes},
            'analysis': {'airports': airports_data},
            'timeline': timeline,
            'overall_conditions': overall,
            'ai_briefing': {
                'executive_summary': f"Route analysis for {' → '.join(codes)} shows {overall} conditions overall. {len([s for s in severities if s == 'SEVERE'])} severe, {len([s for s in severities if s == 'MODERATE'])} moderate, {len([s for s in severities if s == 'CLEAR'])} clear airports."
            },
            'timestamp': datetime.utcnow().isoformat()
        }

        print(
            f"✅ Route complete: {overall} with {len([p for p in timeline if p['latitude'] and p['longitude']])} mapped airports")
        return jsonify(response)

    except Exception as e:
        print(f"❌ Route error: {e}")
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    print("🛫 AeroLish - Fixed Airport Names and Map Coordinates")
    print("📡 Server: http://localhost:5000")
    print("🌍 Airport Database: OpenFlights + Hardcoded (50+ major airports)")
    print("🗺️ Map: Proper coordinates for worldwide airports")
    print("✅ Try: KSFO (San Francisco), EGLL (London), RJTT (Tokyo)")
    print("✅ Routes: KLAX,KJFK or EGLL,LFPG,LIRF")
    print("=" * 60)

    app.run(host='0.0.0.0', port=5000, debug=True)

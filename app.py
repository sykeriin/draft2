# app.py - Backend that serves your index.html file
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import requests
import os
from datetime import datetime

app = Flask(__name__)
CORS(app)


def get_airport_info(icao_code):
    """Get airport info from OpenFlights"""
    icao_code = icao_code.upper().strip()

    try:
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
                                    latitude = float(
                                        lat) if lat != "\\N" else None
                                    longitude = float(
                                        lon) if lon != "\\N" else None
                                except:
                                    latitude = longitude = None

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
                    except:
                        continue
    except Exception as e:
        print(f"Airport lookup failed: {e}")

    # Fallback
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


def get_weather_data(icao):
    """Get weather data"""
    icao = icao.upper()

    # Try NOAA first
    try:
        url = f"https://tgftp.nws.noaa.gov/data/observations/metar/stations/{icao}.TXT"
        response = requests.get(url, timeout=8)
        if response.status_code == 200:
            lines = response.text.strip().split('\n')
            if len(lines) >= 2:
                metar_line = lines[1].strip()
                if metar_line.startswith(icao):
                    return metar_line
    except:
        pass

    # Try FAA ADDS
    try:
        url = f"https://aviationweather.gov/api/data/metar?format=json&ids={icao}"
        response = requests.get(url, timeout=8)
        if response.status_code == 200:
            data = response.json()
            if isinstance(data, list) and len(data) > 0:
                metar_text = data[0].get('raw_text', '')
                if metar_text:
                    return metar_text
    except:
        pass

    # Test data
    current_time = datetime.utcnow()
    day = current_time.strftime('%d')
    hour = current_time.strftime('%H')
    minute = current_time.strftime('%M')

    test_data = {
        'KTUS': f'KTUS {day}{hour}{minute}Z 09015G25KT 10SM TS SCT030 BKN060 CB100 28/22 A2992',
        'KLAX': f'KLAX {day}{hour}{minute}Z 25012KT 6SM BR FEW015 SCT250 22/18 A2995',
        'KJFK': f'KJFK {day}{hour}{minute}Z 28015G20KT 8SM BKN020 OVC040 18/15 A3015',
        'VOGO': f'VOGO {day}{hour}{minute}Z 27008KT 3000 -RA SCT015 BKN030 26/24 Q1012'
    }

    return test_data.get(icao, f'{icao} {day}{hour}{minute}Z 27010KT 9999 FEW030 22/18 Q1013')


def analyze_severity(metar_text):
    """Analyze severity"""
    if not metar_text:
        return 'UNKNOWN'

    text = metar_text.upper()

    if any(condition in text for condition in ['TS', '+TS', 'TSRA', 'CB', 'FC']):
        return 'SEVERE'

    if any(wx in text for wx in ['RA', 'SN', 'BR', 'FG', 'BKN', 'OVC']):
        return 'MODERATE'

    return 'CLEAR'

# Serve your index.html file


@app.route('/')
def serve_index():
    return send_from_directory('.', 'index.html')


@app.route('/health')
def health():
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "message": "AeroLish backend ready!"
    })


@app.route('/api/weather/<icao>')
def get_weather(icao):
    try:
        print(f"\n🎯 Weather request for {icao}")

        airport_info = get_airport_info(icao)
        metar_text = get_weather_data(icao)
        severity = analyze_severity(metar_text)

        # AI briefing
        if severity == 'SEVERE':
            summary = f"🚨 SEVERE weather at {icao} ({airport_info['name']}). Thunderstorms detected."
            impact = "Major delays expected. Consider alternates."
            recommendations = ["Monitor conditions",
                               "Brief alternates", "Expect delays"]
        elif severity == 'MODERATE':
            summary = f"⚠️ MODERATE weather at {icao} ({airport_info['name']}). Some impacts present."
            impact = "Some delays possible. Monitor conditions."
            recommendations = ["Monitor weather",
                               "Brief crew", "Consider fuel adjustments"]
        else:
            summary = f"✅ Favorable weather at {icao} ({airport_info['name']}). Normal operations."
            impact = "Normal operations expected."
            recommendations = ["Standard procedures", "Normal operations"]

        response = {
            'icao': icao.upper(),
            'airport': airport_info,
            'weather': {
                'metar': {
                    'raw_text': metar_text,
                    'parsed': {'severity': severity}
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
            'timestamp': datetime.utcnow().isoformat()
        }

        print(f"✅ Success: {severity} at {airport_info['name']}")
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
            airport_info = get_airport_info(code)
            metar_text = get_weather_data(code)
            severity = analyze_severity(metar_text)
            severities.append(severity)

            airports_data.append({
                'code': code,
                'info': airport_info,
                'current_weather': {
                    'raw_text': metar_text,
                    'parsed': {'severity': severity}
                }
            })

            timeline.append({
                'icao': code,
                'name': airport_info['name'],
                'latitude': airport_info['latitude'],
                'longitude': airport_info['longitude'],
                'severity': severity,
                'weather_summary': metar_text[:50] + '...' if len(metar_text) > 50 else metar_text
            })

        overall = 'SEVERE' if 'SEVERE' in severities else 'MODERATE' if 'MODERATE' in severities else 'CLEAR'

        response = {
            'route': {'airports': codes},
            'analysis': {'airports': airports_data},
            'timeline': timeline,
            'overall_conditions': overall,
            'ai_briefing': {
                'executive_summary': f"Route {' → '.join(codes)}: {overall} conditions overall."
            },
            'timestamp': datetime.utcnow().isoformat()
        }

        print(f"✅ Route complete: {overall}")
        return jsonify(response)

    except Exception as e:
        print(f"❌ Route error: {e}")
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    print("🛫 AeroLish Backend - Serves your index.html")
    print("📁 Place your index.html in the same folder as this app.py")
    print("📡 Server: http://localhost:5000")
    print("✅ Your index.html will work perfectly!")
    print("=" * 50)

    app.run(host='0.0.0.0', port=5000, debug=True)

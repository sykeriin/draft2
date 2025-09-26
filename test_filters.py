#!/usr/bin/env python3

"""
Test script to demonstrate the new TAF, PIREP, SIGMET filtering functionality
"""

import requests
import json

def test_single_airport():
    """Test single airport API with all weather data types"""
    print("🧪 Testing Single Airport API with Additional Weather Data")
    print("=" * 60)
    
    try:
        response = requests.get('http://localhost:5000/api/weather/KTUS')
        if response.status_code == 200:
            data = response.json()
            
            print(f"✅ Airport: {data['airport']['name']} ({data['icao']})")
            print(f"📍 Location: {data['airport']['city']}, {data['airport']['country']}")
            print(f"🌤️  Severity: {data['weather']['metar']['parsed']['severity']}")
            print()
            
            # METAR (with English summary)
            print("📋 METAR (Current Weather):")
            print(f"   English: {data['weather']['metar']['english_summary']}")
            print(f"   Raw: {data['weather']['metar']['raw_text'][:60]}...")
            print()
            
            # TAF
            print("📅 TAF (Terminal Aerodrome Forecast):")
            if data['weather']['taf']['success']:
                print(f"   ✅ {data['weather']['taf']['raw_text']}")
                print(f"   Source: {data['weather']['taf']['source']}")
            else:
                print("   ❌ No TAF data available")
            print()
            
            # PIREP
            print("✈️ PIREP (Pilot Reports):")
            if data['weather']['pirep']['success'] and data['weather']['pirep']['count'] > 0:
                for i, report in enumerate(data['weather']['pirep']['reports']):
                    print(f"   Report {i+1}: {report['raw_text']}")
                print(f"   Source: {data['weather']['pirep'].get('source', 'Unknown')}")
            else:
                print("   ❌ No PIREP data available")
            print()
            
            # SIGMET
            print("⚠️ SIGMET (Significant Meteorological Information):")
            if data['weather']['sigmet']['count'] > 0:
                for i, report in enumerate(data['weather']['sigmet']['reports']):
                    print(f"   Report {i+1}: {report.get('raw_text', 'SIGMET data')}")
            else:
                print("   ❌ No SIGMET data available")
            print()
            
            # AIRMET  
            print("📡 AIRMET (Airmen's Meteorological Information):")
            if data['weather']['airmet']['count'] > 0:
                for i, report in enumerate(data['weather']['airmet']['reports']):
                    print(f"   Report {i+1}: {report.get('raw_text', 'AIRMET data')}")
            else:
                print("   ❌ No AIRMET data available")
            print()
            
            # Winds Aloft
            print("🌬️ Winds Aloft:")
            if data['weather']['winds_aloft']['success']:
                for alt, wind_data in data['weather']['winds_aloft']['altitudes'].items():
                    print(f"   {alt} ft: {wind_data['wind_dir']}°/{wind_data['wind_speed']}kt, Temp: {wind_data['temperature']}°C")
            else:
                print("   ❌ No winds aloft data available")
            print()
            
            print("🎉 All weather data types are now available!")
            print()
            print("📱 Frontend Usage:")
            print("   1. Open http://localhost:5000 in your browser")
            print("   2. Enter airport code (e.g., KTUS)")
            print("   3. Click the filter checkboxes (TAF, PIREP, SIGMET, AIRMET, Winds Aloft)")
            print("   4. Watch the data sections appear/disappear based on your selections!")
            print("   5. DeepSeek will provide English summaries instead of raw METAR codes")
            
        else:
            print(f"❌ API Error: {response.status_code}")
            print(response.text)
            
    except Exception as e:
        print(f"❌ Connection Error: {e}")
        print("Make sure the server is running with: python aerolish_final.py")

if __name__ == "__main__":
    test_single_airport()
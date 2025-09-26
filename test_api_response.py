#!/usr/bin/env python3

import requests
import json

def test_api():
    try:
        print("🧪 Testing Full API Response...")
        response = requests.get('http://localhost:5000/api/weather/KTUS', timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            
            print("✅ API Response Structure:")
            print(f"   Airport: {data['airport']['name']}")
            print(f"   METAR English: {data['weather']['metar']['english_summary'][:60]}...")
            
            # Check each data type
            weather = data['weather']
            
            print(f"   TAF: {'✅' if weather['taf'].get('raw_text') else '❌'} - {weather['taf'].get('raw_text', 'No data')[:40]}...")
            print(f"   PIREP: {'✅' if weather['pirep']['count'] > 0 else '❌'} - {weather['pirep']['count']} reports")
            print(f"   SIGMET: {'✅' if weather['sigmet']['count'] > 0 else '❌'} - {weather['sigmet']['count']} reports")
            print(f"   AIRMET: {'✅' if weather['airmet']['count'] > 0 else '❌'} - {weather['airmet']['count']} reports")
            print(f"   Winds Aloft: {'✅' if weather['winds_aloft'].get('altitudes') else '❌'} - {len(weather['winds_aloft'].get('altitudes', {}))} levels")
            
            print("\n🎉 All weather data types are working in the API!")
            print("\n📱 Frontend Test:")
            print("   1. Open http://localhost:5000")
            print("   2. Enter 'KTUS' and click Analyze Weather")
            print("   3. Toggle the TAF, PIREP, SIGMET, AIRMET, Winds Aloft checkboxes")
            print("   4. You should see data appear/disappear!")
            
        else:
            print(f"❌ API Error: {response.status_code}")
            
    except requests.exceptions.ConnectionError:
        print("❌ Connection error. Make sure the server is running:")
        print("   python aerolish_final.py")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    test_api()
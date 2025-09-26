#!/usr/bin/env python3

"""
Test script to verify the English summary functionality is working correctly
in the AeroLish API responses.
"""

import json
from aerolish_final import get_airport_info, get_weather_data, analyze_severity, get_english_summary

def test_english_summary():
    """Test the English summary generation"""
    print("🧪 Testing English Summary Generation")
    print("=" * 50)
    
    # Test airports
    test_airports = ['KTUS', 'KLAX', 'KJFK', 'VOGO']
    
    for icao in test_airports:
        print(f"\n📍 Testing {icao}:")
        
        # Get airport info
        airport_info = get_airport_info(icao)
        print(f"   Airport: {airport_info['name']} ({airport_info['city']})")
        
        # Get weather data
        metar_text = get_weather_data(icao)
        print(f"   Raw METAR: {metar_text[:60]}...")
        
        # Get English summary
        english_summary = get_english_summary(icao, metar_text)
        print(f"   English: {english_summary}")
        
        # Get severity
        severity = analyze_severity(metar_text)
        print(f"   Severity: {severity}")
        
        print("-" * 40)

def test_api_response_structure():
    """Test that the API response includes the English summary"""
    print("\n🔧 Testing API Response Structure")
    print("=" * 50)
    
    from aerolish_final import app
    
    with app.test_client() as client:
        # Test single airport endpoint
        response = client.get('/api/weather/KTUS')
        if response.status_code == 200:
            data = json.loads(response.data)
            
            print("✅ Single Airport API Response Structure:")
            print(f"   ICAO: {data.get('icao')}")
            print(f"   Airport Name: {data.get('airport', {}).get('name')}")
            print(f"   Has raw_text: {'raw_text' in data.get('weather', {}).get('metar', {})}")
            print(f"   Has english_summary: {'english_summary' in data.get('weather', {}).get('metar', {})}")
            
            if 'english_summary' in data.get('weather', {}).get('metar', {}):
                summary = data['weather']['metar']['english_summary']
                print(f"   English Summary: {summary[:60]}...")
            else:
                print("   ❌ English summary not found in response!")
        else:
            print(f"   ❌ API request failed with status {response.status_code}")
        
        # Test route endpoint
        response = client.get('/api/route?airports=KLAX,KJFK')
        if response.status_code == 200:
            data = json.loads(response.data)
            
            print("\n✅ Route API Response Structure:")
            airports = data.get('analysis', {}).get('airports', [])
            print(f"   Number of airports: {len(airports)}")
            
            for i, airport in enumerate(airports):
                has_english = 'english_summary' in airport.get('current_weather', {})
                print(f"   Airport {i+1} ({airport.get('code')}): Has english_summary = {has_english}")
                
                if has_english:
                    summary = airport['current_weather']['english_summary']
                    print(f"      Summary: {summary[:60]}...")
        else:
            print(f"   ❌ Route API request failed with status {response.status_code}")

if __name__ == "__main__":
    test_english_summary()
    test_api_response_structure()
    print("\n🎉 Testing completed!")
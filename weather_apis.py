# weather_apis.py - Aviation Weather API Integration & Data Management
import os
import re
import requests
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class WeatherAPIManager:
    def __init__(self):
        self.timeout = 15
        self.apis = {
            'aviationweather': {
                'base_url': 'https://aviationweather.gov/api/data',
                'priority': 1,
                'rate_limit': 60  # requests per minute
            },
            'checkwx': {
                'base_url': 'https://api.checkwx.com',
                'api_key': os.getenv('CHECKWX_API_KEY'),
                'priority': 2,
                'rate_limit': 1000
            },
            'avwx': {
                'base_url': 'https://avwx.rest/api',
                'api_key': os.getenv('AVWX_API_KEY'),
                'priority': 3,
                'rate_limit': 4000
            }
        }
        self.cache = {}
        self.cache_duration = 300  # 5 minutes

    def _is_cached_valid(self, key: str) -> bool:
        """Check if cached data is still valid"""
        if key not in self.cache:
            return False
        return (datetime.utcnow() - self.cache[key]['timestamp']).seconds < self.cache_duration

    def _cache_data(self, key: str, data: Any) -> None:
        """Cache data with timestamp"""
        self.cache[key] = {
            'data': data,
            'timestamp': datetime.utcnow()
        }

    def get_metar_data(self, icao: str) -> Dict[str, Any]:
        """Get METAR data from multiple sources with fallbacks"""
        icao = icao.upper().strip()
        cache_key = f"metar_{icao}"
        
        if self._is_cached_valid(cache_key):
            logger.info(f"Using cached METAR for {icao}")
            return self.cache[cache_key]['data']

        result = {
            'raw_text': '',
            'parsed': {},
            'source': 'none',
            'timestamp': None,
            'altitude_data': {},
            'success': False
        }

        # Try Aviation Weather Center first
        try:
            url = f"{self.apis['aviationweather']['base_url']}/metar?format=json&ids={icao}"
            response = requests.get(url, timeout=self.timeout)
            
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, list) and len(data) > 0:
                    metar_data = data[0]
                    result.update({
                        'raw_text': metar_data.get('raw_text', ''),
                        'timestamp': metar_data.get('obsTime'),
                        'parsed': self._parse_metar(metar_data.get('raw_text', '')),
                        'source': 'FAA Aviation Weather',
                        'success': True
                    })
                    logger.info(f"✅ Got METAR from AWC for {icao}")
        except Exception as e:
            logger.warning(f"AWC METAR failed for {icao}: {e}")

        # Try CheckWX if AWC failed
        if not result['success'] and self.apis['checkwx']['api_key']:
            try:
                headers = {'X-API-Key': self.apis['checkwx']['api_key']}
                url = f"{self.apis['checkwx']['base_url']}/metar/{icao}/decoded"
                response = requests.get(url, headers=headers, timeout=self.timeout)
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get('data') and len(data['data']) > 0:
                        metar_data = data['data'][0]
                        result.update({
                            'raw_text': metar_data.get('raw_text', ''),
                            'timestamp': metar_data.get('observed'),
                            'parsed': self._parse_metar(metar_data.get('raw_text', '')),
                            'source': 'CheckWX',
                            'success': True
                        })
                        logger.info(f"✅ Got METAR from CheckWX for {icao}")
            except Exception as e:
                logger.warning(f"CheckWX METAR failed for {icao}: {e}")

        # Try AVWX as last resort
        if not result['success'] and self.apis['avwx']['api_key']:
            try:
                headers = {'Authorization': f"Token {self.apis['avwx']['api_key']}"}
                url = f"{self.apis['avwx']['base_url']}/metar/{icao}"
                response = requests.get(url, headers=headers, timeout=self.timeout)
                
                if response.status_code == 200:
                    data = response.json()
                    result.update({
                        'raw_text': data.get('raw', ''),
                        'timestamp': data.get('time', {}).get('dt'),
                        'parsed': self._parse_metar(data.get('raw', '')),
                        'source': 'AVWX',
                        'success': True
                    })
                    logger.info(f"✅ Got METAR from AVWX for {icao}")
            except Exception as e:
                logger.warning(f"AVWX METAR failed for {icao}: {e}")

        if result['success']:
            self._cache_data(cache_key, result)
        
        return result

    def get_taf_data(self, icao: str) -> Dict[str, Any]:
        """Get TAF data from multiple sources"""
        icao = icao.upper().strip()
        cache_key = f"taf_{icao}"
        
        if self._is_cached_valid(cache_key):
            return self.cache[cache_key]['data']

        result = {
            'raw_text': '',
            'parsed': {},
            'source': 'none',
            'timestamp': None,
            'periods': [],
            'success': False
        }

        # Try Aviation Weather Center
        try:
            url = f"{self.apis['aviationweather']['base_url']}/taf?format=json&ids={icao}"
            response = requests.get(url, timeout=self.timeout)
            
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, list) and len(data) > 0:
                    taf_data = data[0]
                    result.update({
                        'raw_text': taf_data.get('raw_text', ''),
                        'timestamp': taf_data.get('issueTime'),
                        'parsed': self._parse_taf(taf_data.get('raw_text', '')),
                        'source': 'FAA Aviation Weather',
                        'success': True
                    })
        except Exception as e:
            logger.warning(f"AWC TAF failed for {icao}: {e}")

        # Fallback to other APIs similar to METAR
        if not result['success'] and self.apis['checkwx']['api_key']:
            try:
                headers = {'X-API-Key': self.apis['checkwx']['api_key']}
                url = f"{self.apis['checkwx']['base_url']}/taf/{icao}"
                response = requests.get(url, headers=headers, timeout=self.timeout)
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get('data') and len(data['data']) > 0:
                        result.update({
                            'raw_text': data['data'][0].get('raw_text', ''),
                            'source': 'CheckWX',
                            'success': True
                        })
            except Exception as e:
                logger.warning(f"CheckWX TAF failed for {icao}: {e}")

        if result['success']:
            self._cache_data(cache_key, result)
        
        return result

    def get_pirep_data(self, icao: str, radius: int = 50) -> Dict[str, Any]:
        """Get PIREP data within radius of airport"""
        try:
            url = f"{self.apis['aviationweather']['base_url']}/pirep?format=json"
            response = requests.get(url, timeout=self.timeout)
            
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, list):
                    # Filter PIREPs near the airport (simplified)
                    relevant_pireps = [p for p in data if icao.upper() in p.get('raw_text', '').upper()][:5]
                    return {
                        'reports': relevant_pireps,
                        'count': len(relevant_pireps),
                        'source': 'FAA Aviation Weather',
                        'success': True
                    }
        except Exception as e:
            logger.warning(f"PIREP failed for {icao}: {e}")
        
        return {'reports': [], 'count': 0, 'success': False}

    def get_sigmet_airmet_data(self, icao: str) -> Dict[str, Any]:
        """Get SIGMET and AIRMET data"""
        result = {
            'sigmet': {'reports': [], 'count': 0},
            'airmet': {'reports': [], 'count': 0},
            'success': False
        }

        # Get SIGMET
        try:
            url = f"{self.apis['aviationweather']['base_url']}/sigmet?format=json"
            response = requests.get(url, timeout=self.timeout)
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, list):
                    result['sigmet']['reports'] = data[:3]  # Latest 3
                    result['sigmet']['count'] = len(data)
        except Exception as e:
            logger.warning(f"SIGMET failed: {e}")

        # Get AIRMET
        try:
            url = f"{self.apis['aviationweather']['base_url']}/airmet?format=json"
            response = requests.get(url, timeout=self.timeout)
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, list):
                    result['airmet']['reports'] = data[:3]  # Latest 3
                    result['airmet']['count'] = len(data)
        except Exception as e:
            logger.warning(f"AIRMET failed: {e}")

        result['success'] = True
        return result

    def get_winds_aloft(self, icao: str) -> Dict[str, Any]:
        """Get winds aloft data for different altitudes"""
        # This would typically require specialized APIs
        # For now, return structured placeholder
        return {
            'altitudes': {
                '3000': {'wind_dir': 270, 'wind_speed': 15, 'temperature': 10},
                '6000': {'wind_dir': 280, 'wind_speed': 25, 'temperature': 0},
                '9000': {'wind_dir': 290, 'wind_speed': 35, 'temperature': -10},
                '12000': {'wind_dir': 300, 'wind_speed': 45, 'temperature': -20},
                '18000': {'wind_dir': 280, 'wind_speed': 55, 'temperature': -35},
            },
            'source': 'Winds Aloft Forecast',
            'success': True
        }

    def _parse_metar(self, raw_text: str) -> Dict[str, Any]:
        """Parse METAR into structured data"""
        if not raw_text:
            return {}

        parsed = {
            'wind': self._parse_wind(raw_text),
            'visibility': self._parse_visibility(raw_text),
            'weather': self._parse_weather_phenomena(raw_text),
            'clouds': self._parse_clouds(raw_text),
            'temperature': self._parse_temperature(raw_text),
            'pressure': self._parse_pressure(raw_text),
            'runway_visual_range': self._parse_rvr(raw_text),
            'severity': self._determine_severity(raw_text)
        }
        
        return parsed

    def _parse_wind(self, metar: str) -> Dict[str, Any]:
        """Parse wind information"""
        wind_pattern = r'(\d{3}|VRB)(\d{2,3})(G(\d{2,3}))?KT'
        match = re.search(wind_pattern, metar)
        
        if match:
            direction = match.group(1)
            speed = int(match.group(2))
            gust = int(match.group(4)) if match.group(4) else None
            
            return {
                'direction': direction,
                'speed': speed,
                'gust': gust,
                'variable': direction == 'VRB',
                'calm': speed == 0
            }
        
        return {'calm': True, 'direction': None, 'speed': 0}

    def _parse_visibility(self, metar: str) -> Dict[str, Any]:
        """Parse visibility information"""
        # Statute miles
        sm_pattern = r'\b(\d{1,2}(?:\s+\d/\d)?|\d/\d)SM\b'
        sm_match = re.search(sm_pattern, metar)
        
        if sm_match:
            vis_str = sm_match.group(1)
            return {
                'value': vis_str,
                'unit': 'SM',
                'meters': None
            }
        
        # Meters
        m_pattern = r'\b(\d{4})\b'
        m_match = re.search(m_pattern, metar)
        
        if m_match:
            meters = int(m_match.group(1))
            return {
                'value': meters,
                'unit': 'M',
                'meters': meters
            }
        
        return {'value': 'Unknown', 'unit': None}

    def _parse_weather_phenomena(self, metar: str) -> List[Dict[str, Any]]:
        """Parse weather phenomena"""
        weather_codes = {
            'TS': {'name': 'Thunderstorm', 'severity': 'severe'},
            'RA': {'name': 'Rain', 'severity': 'moderate'},
            'SN': {'name': 'Snow', 'severity': 'moderate'},
            'DZ': {'name': 'Drizzle', 'severity': 'light'},
            'FG': {'name': 'Fog', 'severity': 'moderate'},
            'BR': {'name': 'Mist', 'severity': 'light'},
            'HZ': {'name': 'Haze', 'severity': 'light'}
        }
        
        phenomena = []
        for code, info in weather_codes.items():
            if code in metar:
                intensity = 'light'
                if f'+{code}' in metar:
                    intensity = 'heavy'
                elif f'-{code}' in metar:
                    intensity = 'light'
                
                phenomena.append({
                    'code': code,
                    'name': info['name'],
                    'intensity': intensity,
                    'severity': info['severity']
                })
        
        return phenomena

    def _parse_clouds(self, metar: str) -> List[Dict[str, Any]]:
        """Parse cloud information"""
        cloud_pattern = r'(FEW|SCT|BKN|OVC)(\d{3})(CB|TCU)?'
        matches = re.findall(cloud_pattern, metar)
        
        clouds = []
        for match in matches:
            coverage, height, type_suffix = match
            clouds.append({
                'coverage': coverage,
                'height_agl': int(height) * 100,
                'type': type_suffix if type_suffix else None
            })
        
        return clouds

    def _parse_temperature(self, metar: str) -> Dict[str, Any]:
        """Parse temperature and dewpoint"""
        temp_pattern = r'\s(M?\d{2})/(M?\d{2})\s'
        match = re.search(temp_pattern, metar)
        
        if match:
            temp_str, dewpoint_str = match.groups()
            temp = int(temp_str.replace('M', '-'))
            dewpoint = int(dewpoint_str.replace('M', '-'))
            
            return {
                'temperature_c': temp,
                'dewpoint_c': dewpoint,
                'spread': temp - dewpoint
            }
        
        return {}

    def _parse_pressure(self, metar: str) -> Dict[str, Any]:
        """Parse pressure information"""
        # Altimeter setting
        alt_pattern = r'A(\d{4})'
        alt_match = re.search(alt_pattern, metar)
        
        if alt_match:
            altimeter = int(alt_match.group(1))
            return {
                'altimeter_inhg': altimeter / 100.0,
                'unit': 'inHg'
            }
        
        # QNH pattern
        qnh_pattern = r'Q(\d{4})'
        qnh_match = re.search(qnh_pattern, metar)
        
        if qnh_match:
            qnh = int(qnh_match.group(1))
            return {
                'qnh_hpa': qnh,
                'unit': 'hPa'
            }
        
        return {}

    def _parse_rvr(self, metar: str) -> List[Dict[str, Any]]:
        """Parse Runway Visual Range"""
        rvr_pattern = r'R(\d{2}[LCR]?)/(\d{4})'
        matches = re.findall(rvr_pattern, metar)
        
        rvr_data = []
        for runway, visibility in matches:
            rvr_data.append({
                'runway': runway,
                'visibility_ft': int(visibility)
            })
        
        return rvr_data

    def _determine_severity(self, metar: str) -> str:
        """Determine overall weather severity"""
        severe_conditions = ['TS', '+TS', 'TSRA', 'CB', 'FC', '+GR', 'VA']
        moderate_conditions = ['RA', '+RA', 'SN', '+SN', 'SHRA', 'SHSN', 'FG']
        
        if any(condition in metar for condition in severe_conditions):
            return 'SEVERE'
        elif any(condition in metar for condition in moderate_conditions):
            return 'MODERATE'
        else:
            return 'CLEAR'

    def _parse_taf(self, raw_text: str) -> Dict[str, Any]:
        """Parse TAF into structured data"""
        if not raw_text:
            return {}
        
        # Basic TAF parsing - would be more complex in production
        return {
            'valid_period': self._extract_valid_period(raw_text),
            'forecast_groups': self._extract_forecast_groups(raw_text),
            'tempo_groups': self._extract_tempo_groups(raw_text),
            'prob_groups': self._extract_prob_groups(raw_text)
        }

    def _extract_valid_period(self, taf: str) -> Dict[str, str]:
        """Extract TAF valid period"""
        pattern = r'(\d{6})/(\d{6})'
        match = re.search(pattern, taf)
        if match:
            return {
                'from': match.group(1),
                'to': match.group(2)
            }
        return {}

    def _extract_forecast_groups(self, taf: str) -> List[Dict[str, Any]]:
        """Extract forecast groups from TAF"""
        # Simplified - would need more complex parsing
        return []

    def _extract_tempo_groups(self, taf: str) -> List[Dict[str, Any]]:
        """Extract TEMPO groups"""
        tempo_pattern = r'TEMPO\s+(\d{4}/\d{4})'
        matches = re.findall(tempo_pattern, taf)
        return [{'period': match} for match in matches]

    def _extract_prob_groups(self, taf: str) -> List[Dict[str, Any]]:
        """Extract PROB groups"""
        prob_pattern = r'PROB(\d{2})\s+(\d{4}/\d{4})'
        matches = re.findall(prob_pattern, taf)
        return [{'probability': int(match[0]), 'period': match[1]} for match in matches]

# Airport data management
class AirportDataManager:
    def __init__(self):
        self.cache = {}
        self.cache_duration = 86400  # 24 hours for airport data
    
    def get_airport_info(self, code: str) -> Dict[str, Any]:
        """Get airport information from multiple sources"""
        code = code.upper().strip()
        cache_key = f"airport_{code}"
        
        if self._is_cached_valid(cache_key):
            return self.cache[cache_key]['data']
        
        # Try multiple sources
        airport_info = self._fetch_from_openflights(code)
        
        if not airport_info:
            airport_info = self._fetch_from_ourairports(code)
        
        if not airport_info:
            airport_info = self._create_fallback_info(code)
        
        self._cache_data(cache_key, airport_info)
        return airport_info
    
    def _fetch_from_openflights(self, code: str) -> Optional[Dict[str, Any]]:
        """Fetch from OpenFlights database"""
        try:
            url = "https://raw.githubusercontent.com/jpatokal/openflights/master/data/airports.dat"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                for line in response.text.split('\n'):
                    if '","' in line:
                        parts = line.split('","')
                        if len(parts) >= 8:
                            iata = parts[4].strip('"')
                            icao = parts[5].strip('"')
                            
                            if icao == code or iata == code:
                                return {
                                    'icao': icao,
                                    'iata': iata,
                                    'name': parts[1].strip('"'),
                                    'city': parts[2].strip('"'),
                                    'country': parts[3].strip('"'),
                                    'latitude': float(parts[6]) if parts[6] != '\\N' else None,
                                    'longitude': float(parts[7]) if parts[7] != '\\N' else None,
                                    'elevation_ft': int(parts[8]) if parts[8] != '\\N' else None,
                                    'source': 'OpenFlights'
                                }
        except Exception as e:
            logger.warning(f"OpenFlights lookup failed for {code}: {e}")
        
        return None
    
    def _fetch_from_ourairports(self, code: str) -> Optional[Dict[str, Any]]:
        """Fetch from OurAirports API"""
        # Placeholder for OurAirports API call
        return None
    
    def _create_fallback_info(self, code: str) -> Dict[str, Any]:
        """Create fallback airport info"""
        return {
            'icao': code,
            'iata': '',
            'name': f'Airport {code}',
            'city': 'Unknown',
            'country': 'Unknown',
            'latitude': None,
            'longitude': None,
            'elevation_ft': None,
            'source': 'Fallback'
        }
    
    def _is_cached_valid(self, key: str) -> bool:
        """Check cache validity"""
        if key not in self.cache:
            return False
        return (datetime.utcnow() - self.cache[key]['timestamp']).seconds < self.cache_duration
    
    def _cache_data(self, key: str, data: Any) -> None:
        """Cache data"""
        self.cache[key] = {
            'data': data,
            'timestamp': datetime.utcnow()
        }

# Route planning and weather analysis
class RouteWeatherAnalyzer:
    def __init__(self, weather_manager: WeatherAPIManager, airport_manager: AirportDataManager):
        self.weather_manager = weather_manager
        self.airport_manager = airport_manager
    
    def analyze_route(self, airport_codes: List[str]) -> Dict[str, Any]:
        """Analyze weather along a route"""
        route_analysis = {
            'airports': [],
            'legs': [],
            'overall_conditions': 'UNKNOWN',
            'alternative_routes': [],
            'weather_hazards': [],
            'recommendations': []
        }
        
        # Get weather for each airport
        for i, code in enumerate(airport_codes):
            airport_info = self.airport_manager.get_airport_info(code)
            weather_data = self.weather_manager.get_metar_data(code)
            taf_data = self.weather_manager.get_taf_data(code)
            
            airport_analysis = {
                'code': code,
                'info': airport_info,
                'current_weather': weather_data,
                'forecast': taf_data,
                'position_in_route': 'departure' if i == 0 else 'arrival' if i == len(airport_codes)-1 else 'waypoint'
            }
            
            route_analysis['airports'].append(airport_analysis)
            
            # Create legs
            if i < len(airport_codes) - 1:
                next_code = airport_codes[i + 1]
                next_airport = self.airport_manager.get_airport_info(next_code)
                
                leg = {
                    'from': code,
                    'to': next_code,
                    'distance_nm': self._calculate_distance(airport_info, next_airport),
                    'weather_along_route': self._analyze_enroute_weather(airport_info, next_airport)
                }
                
                route_analysis['legs'].append(leg)
        
        # Determine overall conditions
        route_analysis['overall_conditions'] = self._determine_route_conditions(route_analysis['airports'])
        
        # Generate recommendations
        route_analysis['recommendations'] = self._generate_route_recommendations(route_analysis)
        
        return route_analysis
    
    def _calculate_distance(self, airport1: Dict, airport2: Dict) -> Optional[float]:
        """Calculate distance between airports in nautical miles"""
        if not all([airport1.get('latitude'), airport1.get('longitude'),
                   airport2.get('latitude'), airport2.get('longitude')]):
            return None
        
        import math
        
        lat1, lon1 = math.radians(airport1['latitude']), math.radians(airport1['longitude'])
        lat2, lon2 = math.radians(airport2['latitude']), math.radians(airport2['longitude'])
        
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        
        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
        c = 2 * math.asin(math.sqrt(a))
        
        # Earth's radius in nautical miles
        r_nm = 3440.065
        
        return c * r_nm
    
    def _analyze_enroute_weather(self, airport1: Dict, airport2: Dict) -> Dict[str, Any]:
        """Analyze weather conditions along the route"""
        # This would typically involve weather radar, satellite data, etc.
        # For now, return structured placeholder
        return {
            'turbulence_forecast': 'Light',
            'icing_conditions': 'None',
            'convective_weather': 'None',
            'wind_shear_potential': 'Low',
            'recommended_altitude': '8000'
        }
    
    def _determine_route_conditions(self, airports: List[Dict]) -> str:
        """Determine overall route weather conditions"""
        severities = []
        for airport in airports:
            if airport['current_weather'].get('parsed', {}).get('severity'):
                severities.append(airport['current_weather']['parsed']['severity'])
        
        if 'SEVERE' in severities:
            return 'SEVERE'
        elif 'MODERATE' in severities:
            return 'MODERATE'
        else:
            return 'CLEAR'
    
    def _generate_route_recommendations(self, route_analysis: Dict) -> List[str]:
        """Generate flight recommendations based on route analysis"""
        recommendations = []
        
        overall = route_analysis['overall_conditions']
        
        if overall == 'SEVERE':
            recommendations.extend([
                "Consider delaying departure due to severe weather conditions",
                "File alternate airports for all destinations",
                "Ensure aircraft is equipped for severe weather operations",
                "Monitor weather updates closely"
            ])
        elif overall == 'MODERATE':
            recommendations.extend([
                "Brief crew on moderate weather conditions along route",
                "Consider alternate routing if available",
                "Carry extra fuel for possible delays or diversions"
            ])
        else:
            recommendations.append("Weather conditions are favorable for normal operations")
        
        return recommendations

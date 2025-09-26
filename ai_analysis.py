# ai_analysis.py - GenAI Integration for Weather Analysis (DeepSeek primary, Gemini fallback)

import os
import json
import logging
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

DEEPSEEK_BASE = "https://api.deepseek.com"   # OpenAI-compatible base
DEEPSEEK_MODEL = "deepseek-chat"             # concise chat model

class WeatherAIAnalyst:
    def __init__(self):
        # Primary: DeepSeek
        self.deepseek_api_key = os.getenv("DEEPSEEK_API_KEY")
        # Fallback: Gemini
        self.gemini_api_key = os.getenv("GEMINI_API_KEY")

    # ---------------- public API ----------------
    def generate_pilot_briefing(self, weather_data: Dict[str, Any], route_info: Dict[str, Any]) -> Dict[str, Any]:
        """Generate comprehensive pilot briefing using AI"""
        context = self._prepare_weather_context(weather_data, route_info)
        return {
            'executive_summary': self._generate_executive_summary(context),
            'detailed_analysis': self._generate_detailed_analysis(context),
            'operational_impact': self._generate_operational_impact(context),
            'altitude_specific': self._generate_altitude_analysis(context),
            'timing_considerations': self._generate_timing_analysis(context),
            'risk_assessment': self._generate_risk_assessment(context),
            'recommendations': self._generate_recommendations(context),
            'plain_english': self._generate_plain_english_summary(context),
        }

    # ---------------- context builder ----------------
    def _prepare_weather_context(self, weather_data: Dict, route_info: Dict) -> str:
        """Prepare structured context for AI analysis"""
        parts = []

        # Route info
        if route_info.get('airports'):
            airports = [a['code'] for a in route_info['airports']]
            parts.append(f"ROUTE: {' -> '.join(airports)}")

        # Weather per airport
        for airport in route_info.get('airports', []):
            code = airport['code']
            current = airport.get('current_weather', {})
            if current.get('raw_text'):
                parts.append(f"METAR {code}: {current['raw_text']}")
            forecast = airport.get('forecast', {})
            if forecast.get('raw_text'):
                parts.append(f"TAF {code}: {forecast['raw_text']}")

        # Overall notes
        if route_info.get('overall_conditions'):
            parts.append(f"OVERALL CONDITIONS: {route_info['overall_conditions']}")

        return "\n".join(parts)

    # ---------------- section generators ----------------
    def _generate_executive_summary(self, context: str) -> str:
        prompt = f"""
You are an experienced flight dispatcher and meteorologist. Based on the following weather data,
provide a concise executive summary for pilots in 2–3 sentences that covers the most critical information:

{context}

Focus on:
- Overall flight conditions (GO/NO-GO/MONITOR)
- Most significant weather threats
- Key decision points

Write in professional aviation terminology but keep it concise and actionable.
"""
        return self._call_ai_service(prompt, max_tokens=150)

    def _generate_detailed_analysis(self, context: str) -> str:
        prompt = f"""
You are a certified meteorologist providing detailed weather analysis for aviation operations.
Based on the following weather data, provide a comprehensive analysis:

{context}

Structure your analysis to cover:
1. Current conditions at each airport
2. Forecast trends and timing
3. Weather phenomena and their aviation impacts
4. Visibility and ceiling considerations
5. Wind patterns and potential turbulence
6. Precipitation and icing threats

Use technical meteorological terms but explain their operational significance.
Keep the analysis detailed but structured with clear headings.
"""
        return self._call_ai_service(prompt, max_tokens=800)

    def _generate_operational_impact(self, context: str) -> str:
        prompt = f"""
You are an airline operations manager assessing the operational impact of weather conditions.
Based on the following weather data, analyze the operational implications:

{context}

Address:
- Potential delays and their causes
- Fuel planning considerations
- Alternate airport requirements
- Crew duty time impacts
- Passenger service implications
- Aircraft performance factors

Provide specific, actionable insights for flight operations.
"""
        return self._call_ai_service(prompt, max_tokens=600)

    def _generate_altitude_analysis(self, context: str) -> Dict[str, str]:
        """Returns {band: text} for four altitude bands."""
        bands = ['Surface-3000ft', '3000-10000ft', '10000-18000ft', '18000ft+']
        out: Dict[str, str] = {}
        for band in bands:
            prompt = f"""
You are an aviation meteorologist analyzing weather conditions at {band} altitude band.
Based on the following weather data, provide altitude-specific analysis:

{context}

For {band}, analyze:
- Wind conditions (speed, direction, shear potential)
- Temperature and icing conditions
- Turbulence potential
- Visibility restrictions
- Cloud layers and precipitation
- Recommended flight levels

Keep the analysis specific to this altitude band and operationally relevant.
"""
            out[band] = self._call_ai_service(prompt, max_tokens=300)
        return out

    def _generate_timing_analysis(self, context: str) -> str:
        prompt = f"""
You are a flight planning specialist analyzing weather timing for aviation operations.
Based on the following weather data and forecasts, provide timing analysis:

{context}

Analyze:
- Optimal departure windows
- Weather improvement/deterioration trends
- Critical timing for weather changes
- Forecast confidence levels
- Window of opportunity for operations

Provide specific timing recommendations with confidence levels.
"""
        return self._call_ai_service(prompt, max_tokens=400)

    def _generate_risk_assessment(self, context: str) -> Dict[str, Any]:
        prompt = f"""
You are a flight safety officer conducting weather risk assessment.
Based on the following weather data, assess operational risks:

{context}

Provide risk assessment in JSON format with these categories:
- overall_risk_level: (LOW/MODERATE/HIGH/SEVERE)
- primary_risks: [list of main weather risks]
- secondary_risks: [list of secondary concerns]
- mitigation_strategies: [list of risk mitigation actions]
- confidence_level: (HIGH/MEDIUM/LOW)
- monitoring_points: [list of conditions to monitor]

Return only valid JSON.
"""
        response = self._call_ai_service(prompt, max_tokens=400)
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            return {
                'overall_risk_level': 'MODERATE',
                'primary_risks': ['Unable to parse AI response'],
                'secondary_risks': [],
                'mitigation_strategies': ['Manual weather analysis required'],
                'confidence_level': 'LOW',
                'monitoring_points': ['Monitor weather updates'],
            }

    def _generate_recommendations(self, context: str) -> List[str]:
        prompt = f"""
You are an experienced chief pilot providing operational recommendations based on weather conditions.
Based on the following weather data, provide specific, actionable recommendations:

{context}

Provide recommendations as a simple list, each on a new line, covering:
- Go/No-go decision factors
- Fuel planning adjustments
- Route modifications
- Altitude considerations
- Equipment requirements
- Crew briefing points
- Passenger considerations

Format as bullet points, be specific and actionable.
"""
        response = self._call_ai_service(prompt, max_tokens=300)
        recs: List[str] = []
        for line in response.splitlines():
            line = line.strip()
            if not line:
                continue
            if line.startswith(('•', '-', '*')):
                recs.append(line.lstrip('•-* ').strip())
            elif not any(k in line for k in [':', 'based on', 'following']):
                recs.append(line)
        return recs[:8]

    def _generate_plain_english_summary(self, context: str) -> str:
        prompt = f"""
You are explaining weather conditions to passengers and non-technical staff.
Based on the following aviation weather data, provide a clear, plain English summary:

{context}

Write in simple terms that anyone can understand:
- What the weather is like now
- What to expect during the flight
- Any potential impacts on comfort or timing
- Overall outlook (good/challenging/concerning)

Avoid technical jargon and focus on passenger-relevant information.
Keep it reassuring but honest about conditions.
"""
        return self._call_ai_service(prompt, max_tokens=200)

    # ---------------- provider selection ----------------
    def _call_ai_service(self, prompt: str, max_tokens: int = 500) -> str:
        # Try DeepSeek first
        if self.deepseek_api_key:
            try:
                out = self._call_deepseek(prompt, max_tokens)
                if out:
                    logger.info("GenAI provider used: DeepSeek")
                    return out
            except Exception as e:
                logger.warning(f"DeepSeek call failed: {e}")

        # Fallback: Gemini
        if self.gemini_api_key:
            try:
                out = self._call_gemini(prompt, max_tokens)
                if out:
                    logger.info("GenAI provider used: Gemini")
                    return out
            except Exception as e:
                logger.warning(f"Gemini call failed: {e}")

        return "AI analysis temporarily unavailable. Please refer to raw weather data for manual interpretation."

    # ---------------- DeepSeek (primary) ----------------
    def _call_deepseek(self, prompt: str, max_tokens: int) -> Optional[str]:
        """
        Calls DeepSeek via OpenAI-compatible SDK.
        Best practice: low temperature for factual aviation briefings.
        """
        try:
            from openai import OpenAI  # pip install openai>=1.0.0
            client = OpenAI(api_key=self.deepseek_api_key, base_url=DEEPSEEK_BASE)
            resp = client.chat.completions.create(
                model=DEEPSEEK_MODEL,
                messages=[
                    {"role": "system",
                     "content": "You are an expert aviation meteorologist and flight operations specialist. "
                                "Preserve all numbers/units exactly. Lead with hazards. "
                                "Keep 1–3 sentences unless asked for more."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1,
                max_tokens=max_tokens,
            )
            return resp.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"DeepSeek API error: {e}")
            return None

    # ---------------- Gemini (fallback) ----------------
    def _call_gemini(self, prompt: str, max_tokens: int) -> Optional[str]:
        """
        Calls Gemini Developer API (text-only).
        Tries new google-genai client first, then older google-generativeai.
        """
        # New SDK
        try:
            from google import genai  # pip install google-genai
            client = genai.Client(api_key=self.gemini_api_key)
            resp = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=prompt,
                config={"max_output_tokens": max_tokens, "temperature": 0.2},
            )
            return (getattr(resp, "text", "") or "").strip()
        except Exception:
            # Older SDK
            try:
                import google.generativeai as genai_old
                genai_old.configure(api_key=self.gemini_api_key)
                model = genai_old.GenerativeModel("gemini-1.5-flash")
                resp = model.generate_content(
                    prompt,
                    generation_config=genai_old.types.GenerationConfig(
                        max_output_tokens=max_tokens, temperature=0.2
                    ),
                )
                return (getattr(resp, "text", "") or "").strip()
            except Exception as e2:
                logger.error(f"Gemini API error: {e2}")
                return None


class WeatherInsightGenerator:
    """Generate additional weather insights and predictions"""

    def __init__(self, ai_analyst: WeatherAIAnalyst):
        self.ai_analyst = ai_analyst

    def generate_trend_analysis(self, historical_data: List[Dict], current_data: Dict) -> Dict[str, Any]:
        """Stub for trend analysis"""
        return {
            'trend_direction': 'improving',
            'confidence': 'high',
            'expected_changes': [],
            'time_to_change': '2-4 hours',
        }

    def generate_alternative_routes(self, primary_route: List[str], weather_data: Dict) -> List[Dict]:
        """Stub for alternate routing"""
        alternatives: List[Dict[str, Any]] = []
        if len(primary_route) >= 2:
            alternatives.append({
                'route': primary_route,
                'weather_score': 7.5,
                'estimated_time': '2h 15m',
                'fuel_impact': '+5%',
                'reason': 'Avoid convective weather',
            })
        return alternatives

    def generate_weather_alerts(self, route_analysis: Dict) -> List[Dict[str, Any]]:
        """Simple severe alerts from parsed severity"""
        alerts: List[Dict[str, Any]] = []
        for airport in route_analysis.get('airports', []):
            parsed = airport.get('current_weather', {}).get('parsed', {})
            if parsed.get('severity') == 'SEVERE':
                code = airport.get('code', 'UNKNOWN')
                alerts.append({
                    'type': 'WARNING',
                    'location': code,
                    'message': f"Severe weather conditions at {code}",
                    'impact': 'High',
                    'action_required': 'Consider alternate airport',
                })
        return alerts


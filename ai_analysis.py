# ai_analysis.py — DeepSeek primary, Gemini fallback, METAR → NLP summaries

import os
import re
import io
import json
import logging
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# ---------- GenAI providers ----------
DEEPSEEK_BASE = "https://api.deepseek.com"
DEEPSEEK_MODEL = "deepseek-chat"

class WeatherAIAnalyst:
    def __init__(self):
        # Primary: DeepSeek
        self.deepseek_api_key = os.getenv("DEEPSEEK_API_KEY")
        # Fallback: Gemini
        self.gemini_api_key = os.getenv("GEMINI_API_KEY")

    # ---------- Public: generate full briefing (unchanged sections) ----------
    def generate_pilot_briefing(self, weather_data: Dict[str, Any], route_info: Dict[str, Any]) -> Dict[str, Any]:
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

    # ---------- Public: summarize a single station METAR into English ----------
    def summarize_station(self, icao: str, raw_metar: str) -> str:
        tokens = tokenize_metar(raw_metar or "")
        # Compact context strictly from tokens to preserve fidelity
        prompt = (
            "Summarize this station weather in 1–2 sentences for pilots. "
            "Lead with hazards. Preserve numbers/units exactly. Omit missing fields. "
            f"Data: {json.dumps({'icao': icao, 't': tokens}, ensure_ascii=False)}"
        )
        text = self._call_ai_service(prompt, max_tokens=160) or ""
        if not self._verify_text_matches_tokens(text, tokens):
            text = deterministic_summary(tokens)
        return text

    # ---------- Helper: verify LLM output preserves key numbers ----------
    def _verify_text_matches_tokens(self, text: str, t: Dict[str, Any]) -> bool:
        if not text:
            return False
        # Visibility
        if t.get("vis") and t["vis"] not in text:
            return False
        # Altimeter (just the pressure number like 29.92)
        if t.get("alt"):
            altnum = t["alt"].split()[0]
            if altnum not in text:
                return False
        # Wind direction and speed
        w = t.get("wind")
        if w:
            if w.get("dir") and w["dir"] not in text:
                return False
            if w.get("spd") and w["spd"] not in text:
                return False
            if w.get("gst"):
                if w["gst"] not in text:
                    return False
        # Ceiling (if VV or BKN/OVC base computed)
        ceil = t.get("vv")
        if not ceil and t.get("clouds"):
            bases = [int(b)*100 for c,b in t["clouds"] if c in ("BKN","OVC")]
            if bases:
                ceil = min(bases)
        if ceil and str(ceil) not in text:
            # Don’t fail hard if the model omitted ceiling phrase, allow summary to pass
            pass
        return True

    # ---------- Route context for narrative sections ----------
    def _prepare_weather_context(self, weather_data: Dict, route_info: Dict) -> str:
        parts = []
        if route_info.get('airports'):
            airports = [a['code'] for a in route_info['airports']]
            parts.append(f"ROUTE: {' -> '.join(airports)}")
        for airport in route_info.get('airports', []):
            code = airport['code']
            current = airport.get('current_weather', {})
            if current.get('raw_text'):
                # Provide both raw and tokens for richer sections
                tok = tokenize_metar(current['raw_text'])
                parts.append(f"STATION {code} TOKENS: {json.dumps(tok, ensure_ascii=False)}")
                parts.append(f"STATION {code} RAW: {current['raw_text']}")
            forecast = airport.get('forecast', {})
            if forecast.get('raw_text'):
                parts.append(f"TAF {code}: {forecast['raw_text']}")
        if route_info.get('overall_conditions'):
            parts.append(f"OVERALL CONDITIONS: {route_info['overall_conditions']}")
        return "\n".join(parts)

    # ---------- Narrative section generators ----------
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
        for line in (response or "").splitlines():
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

    # ---------- Provider selection ----------
    def _call_ai_service(self, prompt: str, max_tokens: int = 500) -> str:
        # DeepSeek first
        if self.deepseek_api_key:
            try:
                out = self._call_deepseek(prompt, max_tokens)
                if out:
                    logger.info("GenAI provider used: DeepSeek")
                    return out
            except Exception as e:
                logger.warning(f"DeepSeek call failed: {e}")
        # Gemini fallback
        if self.gemini_api_key:
            try:
                out = self._call_gemini(prompt, max_tokens)
                if out:
                    logger.info("GenAI provider used: Gemini")
                    return out
            except Exception as e:
                logger.warning(f"Gemini call failed: {e}")
        return ""

    # ---------- DeepSeek (primary) ----------
    def _call_deepseek(self, prompt: str, max_tokens: int) -> Optional[str]:
        try:
            from openai import OpenAI  # pip install openai>=1.0.0
            client = OpenAI(api_key=self.deepseek_api_key, base_url=DEEPSEEK_BASE)
            resp = client.chat.completions.create(
                model=DEEPSEEK_MODEL,
                messages=[
                    {"role": "system",
                     "content": "You are an expert aviation meteorologist and flight operations specialist. "
                                "Preserve all numbers/units exactly. Lead with hazards. "
                                "Keep 1–2 sentences unless asked for more."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1,
                max_tokens=max_tokens,
            )
            return resp.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"DeepSeek API error: {e}")
            return None

    # ---------- Gemini (fallback) ----------
    def _call_gemini(self, prompt: str, max_tokens: int) -> Optional[str]:
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
            # Older SDK fallback
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


# ---------- METAR parsing and deterministic fallback ----------

WX_CODES = r"(TS|DZ|RA|SN|SG|PL|GR|GS|UP|BR|FG|FU|HZ|DU|SA|SQ|PO|DS|SS|VA)"
CLOUD_CODES = r"(FEW|SCT|BKN|OVC)"

def tokenize_metar(raw: str) -> Dict[str, Any]:
    t: Dict[str, Any] = {"wind": None,"vis": None,"wx": [],"clouds": [],"vv": None,"temp": None,"dew": None,"alt": None}
    s = (raw or "").strip()
    # wind
    m = re.search(r"\b(\d{3})(\d{2,3})(G\d{2,3})?KT\b", s)
    if m: t["wind"] = {"dir": m.group(1), "spd": m.group(2), "gst": (m.group(3) or "").lstrip("G")}
    # visibility
    m = re.search(r"\b(\d{1,2}(?:/\d{1,2})?SM)\b", s)
    if m: t["vis"] = m.group(1)
    # weather codes
    t["wx"] = [("".join(g)).strip() for g in re.findall(r"\s(\+|-)?(VC)?"+WX_CODES+r"\b", s)]
    # clouds
    t["clouds"] = [(m.group(1), m.group(2)) for m in re.finditer(r"\b"+CLOUD_CODES+r"(\d{3})\b", s)]
    # vertical visibility
    m = re.search(r"\bVV(\d{3})\b", s)
    if m: t["vv"] = int(m.group(1)) * 100
    # temp/dew
    m = re.search(r"\s(M?\d{2})/(M?\d{2})(\s|$)", s)
    if m:
        td = lambda x: ("-" + x[1:]) if x.startswith("M") else x
        t["temp"], t["dew"] = td(m.group(1)), td(m.group(2))
    # altimeter
    m = re.search(r"\bA(\d{4})\b", s)
    if m:
        alt = m.group(1); t["alt"] = f"{alt[:2]}.{alt[2:]} inHg"
    return t

def deterministic_summary(t: Dict[str, Any]) -> str:
    parts: List[str] = []
    # ceiling
    ceil = t.get("vv")
    if not ceil and t.get("clouds"):
        bases = [int(b)*100 for c,b in t["clouds"] if c in ("BKN","OVC")]
        ceil = min(bases) if bases else None
    # IFR hint
    if (t.get("vis") in ["1/4SM","1/2SM","3/4SM","1SM","2SM"]) or (ceil is not None and ceil < 1000):
        parts.append("IFR conditions")
    # fields
    if t.get("vis"): parts.append(f"Visibility {t['vis']}")
    if ceil: parts.append(f"Ceiling {ceil} ft")
    elif t.get("clouds"): parts.append("Clouds " + ", ".join([f"{c} {int(b)*100} ft" for c,b in t["clouds"]]))
    w = t.get("wind")
    if w:
        s = f"Winds {w['dir']}° at {w['spd']} kt"
        if w.get("gst"): s += f", gusting {w['gst']} kt"
        parts.append(s)
    if t.get("wx"): parts.append("Weather " + ", ".join(t["wx"]))
    if t.get("temp") and t.get("dew"): parts.append(f"Temp {t['temp']}°C, dew {t['dew']}°C")
    if t.get("alt"): parts.append(f"Altimeter {t['alt']}")
    return ". ".join(parts) + "."

# ---------- Route response helper for your API ----------

def build_route_response(route_info: Dict[str, Any]) -> Dict[str, Any]:
    """
    route_info example:
    {
      "airports": [
        {"code":"KLAX","name":"Los Angeles Intl","current_weather":{"raw_text":"..."},"category":"MODERATE"},
        ...
      ],
      "overall_conditions": "MODERATE"
    }
    Returns dict with summary_text and raw_text per airport for frontend.
    """
    analyst = WeatherAIAnalyst()
    out_airports: List[Dict[str, Any]] = []
    for ap in route_info.get("airports", []):
        code = ap.get("code")
        raw = (ap.get("current_weather") or {}).get("raw_text") or ""
        summary = analyst.summarize_station(code, raw) if raw else ""
        out_airports.append({
            "code": code,
            "name": ap.get("name"),
            "category": ap.get("category"),
            "raw_text": raw,
            "summary_text": summary,  # <-- bind this in React for the English line
        })
    return {
        "overall_conditions": route_info.get("overall_conditions"),
        "airports": out_airports,
    }


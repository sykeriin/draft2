# ai_analysis.py - GenAI Integration for Weather Analysis
import os
import json
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class WeatherAIAnalyst:
    def __init__(self):
        self.openai_api_key = os.getenv('OPENAI_API_KEY')
        self.gemini_api_key = os.getenv('GEMINI_API_KEY')
        self.claude_api_key = os.getenv('CLAUDE_API_KEY')
        
    def generate_pilot_briefing(self, weather_data: Dict[str, Any], route_info: Dict[str, Any]) -> Dict[str, Any]:
        """Generate comprehensive pilot briefing using AI"""
        
        # Prepare context for AI
        context = self._prepare_weather_context(weather_data, route_info)
        
        # Generate different types of briefings
        briefing = {
            'executive_summary': self._generate_executive_summary(context),
            'detailed_analysis': self._generate_detailed_analysis(context),
            'operational_impact': self._generate_operational_impact(context),
            'altitude_specific': self._generate_altitude_analysis(context),
            'timing_considerations': self._generate_timing_analysis(context),
            'risk_assessment': self._generate_risk_assessment(context),
            'recommendations': self._generate_recommendations(context),
            'plain_english': self._generate_plain_english_summary(context)
        }
        
        return briefing
    
    def _prepare_weather_context(self, weather_data: Dict, route_info: Dict) -> str:
        """Prepare structured context for AI analysis"""
        context_parts = []
        
        # Add route information
        if route_info.get('airports'):
            airports = [airport['code'] for airport in route_info['airports']]
            context_parts.append(f"ROUTE: {' -> '.join(airports)}")
        
        # Add weather data for each airport
        for airport in route_info.get('airports', []):
            code = airport['code']
            current = airport.get('current_weather', {})
            
            if current.get('raw_text'):
                context_parts.append(f"METAR {code}: {current['raw_text']}")
            
            forecast = airport.get('forecast', {})
            if forecast.get('raw_text'):
                context_parts.append(f"TAF {code}: {forecast['raw_text']}")
        
        # Add route analysis
        if route_info.get('overall_conditions'):
            context_parts.append(f"OVERALL CONDITIONS: {route_info['overall_conditions']}")
        
        return '\n'.join(context_parts)
    
    def _generate_executive_summary(self, context: str) -> str:
        """Generate executive summary for pilots"""
        prompt = f"""
        You are an experienced flight dispatcher and meteorologist. Based on the following weather data, 
        provide a concise executive summary for pilots in 2-3 sentences that covers the most critical information:

        {context}

        Focus on:
        - Overall flight conditions (GO/NO-GO/MONITOR)
        - Most significant weather threats
        - Key decision points
        
        Write in professional aviation terminology but keep it concise and actionable.
        """
        
        return self._call_ai_service(prompt, max_tokens=150)
    
    def _generate_detailed_analysis(self, context: str) -> str:
        """Generate detailed meteorological analysis"""
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
        """Generate operational impact assessment"""
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
        """Generate altitude-specific weather analysis"""
        altitude_bands = ['Surface-3000ft', '3000-10000ft', '10000-18000ft', '18000ft+']
        altitude_analysis = {}
        
        for band in altitude_bands:
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
            
            altitude_analysis[band] = self._call_ai_service(prompt, max_tokens=300)
        
        return altitude_analysis
    
    def _generate_timing_analysis(self, context: str) -> str:
        """Generate timing-specific weather analysis"""
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
        """Generate comprehensive risk assessment"""
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
                'monitoring_points': ['Monitor weather updates']
            }
    
    def _generate_recommendations(self, context: str) -> List[str]:
        """Generate specific operational recommendations"""
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
        
        # Parse response into list
        recommendations = []
        for line in response.split('\n'):
            line = line.strip()
            if line and (line.startswith('•') or line.startswith('-') or line.startswith('*')):
                recommendations.append(line.lstrip('•-* '))
            elif line and not any(char in line for char in [':', 'based on', 'following']):
                recommendations.append(line)
        
        return recommendations[:8]  # Limit to 8 recommendations
    
    def _generate_plain_english_summary(self, context: str) -> str:
        """Generate plain English summary for non-technical audiences"""
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
    
    def _call_ai_service(self, prompt: str, max_tokens: int = 500) -> str:
        """Call AI service with fallback options"""
        
        # Try OpenAI first
        if self.openai_api_key:
            try:
                response = self._call_openai(prompt, max_tokens)
                if response:
                    return response
            except Exception as e:
                logger.warning(f"OpenAI call failed: {e}")
        
        # Try Gemini as fallback
        if self.gemini_api_key:
            try:
                response = self._call_gemini(prompt, max_tokens)
                if response:
                    return response
            except Exception as e:
                logger.warning(f"Gemini call failed: {e}")
        
        # Try Claude as final fallback
        if self.claude_api_key:
            try:
                response = self._call_claude(prompt, max_tokens)
                if response:
                    return response
            except Exception as e:
                logger.warning(f"Claude call failed: {e}")
        
        # Fallback response
        return "AI analysis temporarily unavailable. Please refer to raw weather data for manual interpretation."
    
    def _call_openai(self, prompt: str, max_tokens: int) -> Optional[str]:
        """Call OpenAI API"""
        try:
            import openai
            openai.api_key = self.openai_api_key
            
            response = openai.ChatCompletion.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are an expert aviation meteorologist and flight operations specialist."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=max_tokens,
                temperature=0.3
            )
            
            return response.choices[0].message.content.strip()
        
        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            return None
    
    def _call_gemini(self, prompt: str, max_tokens: int) -> Optional[str]:
        """Call Google Gemini API"""
        try:
            import google.generativeai as genai
            
            genai.configure(api_key=self.gemini_api_key)
            model = genai.GenerativeModel('gemini-pro')
            
            response = model.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    max_output_tokens=max_tokens,
                    temperature=0.3
                )
            )
            
            return response.text.strip()
        
        except Exception as e:
            logger.error(f"Gemini API error: {e}")
            return None
    
    def _call_claude(self, prompt: str, max_tokens: int) -> Optional[str]:
        """Call Anthropic Claude API"""
        try:
            import anthropic
            
            client = anthropic.Anthropic(api_key=self.claude_api_key)
            
            response = client.messages.create(
                model="claude-3-sonnet-20240229",
                max_tokens=max_tokens,
                temperature=0.3,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            
            return response.content[0].text.strip()
        
        except Exception as e:
            logger.error(f"Claude API error: {e}")
            return None

class WeatherInsightGenerator:
    """Generate additional weather insights and predictions"""
    
    def __init__(self, ai_analyst: WeatherAIAnalyst):
        self.ai_analyst = ai_analyst
    
    def generate_trend_analysis(self, historical_data: List[Dict], current_data: Dict) -> Dict[str, Any]:
        """Generate weather trend analysis"""
        # This would analyze historical patterns and predict trends
        return {
            'trend_direction': 'improving',
            'confidence': 'high',
            'expected_changes': [],
            'time_to_change': '2-4 hours'
        }
    
    def generate_alternative_routes(self, primary_route: List[str], weather_data: Dict) -> List[Dict]:
        """Generate alternative route suggestions based on weather"""
        # This would suggest alternate routing based on weather patterns
        alternatives = []
        
        # Placeholder for route optimization logic
        if len(primary_route) >= 2:
            alternatives.append({
                'route': primary_route,
                'weather_score': 7.5,
                'estimated_time': '2h 15m',
                'fuel_impact': '+5%',
                'reason': 'Avoid convective weather'
            })
        
        return alternatives
    
    def generate_weather_alerts(self, route_analysis: Dict) -> List[Dict[str, Any]]:
        """Generate weather alerts and warnings"""
        alerts = []
        
        # Check for severe conditions
        for airport in route_analysis.get('airports', []):
            weather = airport.get('current_weather', {})
            parsed = weather.get('parsed', {})
            
            if parsed.get('severity') == 'SEVERE':
                alerts.append({
                    'type': 'WARNING',
                    'location': airport['code'],
                    'message': f"Severe weather conditions at {airport['code']}",
                    'impact': 'High',
                    'action_required': 'Consider alternate airport'
                })
        
        return alerts

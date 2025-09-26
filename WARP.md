# WARP.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

## Project Overview

AeroLish is a comprehensive aviation weather intelligence application that provides real-time weather analysis and operational decision support for pilots and aviation professionals. The system features:

- Multi-source weather data integration (NOAA, FAA ADDS, CheckWX, AVWX)
- AI-powered weather analysis using DeepSeek and Gemini models
- Interactive mapping with route visualization
- METAR/TAF parsing and interpretation
- Operational decision support with alternate airport recommendations

## Development Commands

### Environment Setup
```bash
# Create and activate virtual environment
python -m venv .venv
# On Windows:
.venv\Scripts\activate
# On Unix/macOS:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Running the Application
```bash
# Start the Flask development server
python app.py
# Or run the complete version with operational optimizer
python aerolish_final.py

# Server will start on http://localhost:5000
```

### Testing Individual Components
```bash
# Test weather API functionality
python -c "from weather_apis import WeatherAPIManager; mgr = WeatherAPIManager(); print(mgr.get_metar_data('KTUS'))"

# Test AI analysis
python -c "from ai_analysis import WeatherAIAnalyst; analyst = WeatherAIAnalyst(); print(analyst.summarize_station('KTUS', 'KTUS 281253Z 09015G25KT 10SM TS SCT030 BKN060 CB100 28/22 A2992 RMK AO2'))"

# Test airport lookup
python -c "from app import get_airport_info; print(get_airport_info('KTUS'))"
```

### Health Checks
```bash
# Check server health
curl http://localhost:5000/health

# Test single airport endpoint
curl "http://localhost:5000/api/weather/KTUS"

# Test route analysis endpoint
curl "http://localhost:5000/api/route?airports=KLAX,KJFK"
```

## Architecture Overview

### Core Components

**Frontend (index.html)**
- Single-page application with vanilla JavaScript
- Interactive Leaflet maps for route visualization  
- Responsive design with dark/light theme support
- Real-time weather data display with severity indicators

**Main Application (app.py / aerolish_final.py)**
- Flask REST API server with CORS support
- Weather data aggregation from multiple sources
- Airport information lookup via OpenFlights database
- Severity analysis and operational decision engine

**Weather Integration (weather_apis.py)**
- Multi-source weather API management with fallbacks
- METAR/TAF parsing and structured data extraction
- Caching layer for performance optimization
- Rate limiting and error handling

**AI Analysis (ai_analysis.py)**
- DeepSeek (primary) and Gemini (fallback) integration
- METAR tokenization and deterministic parsing fallbacks
- Comprehensive weather briefing generation
- Route-level weather analysis and recommendations

**Configuration (config.py)**
- Environment-based configuration management
- API key management and safety configuration
- Hardcoded airport database for major Indian airports

### Data Flow Architecture

1. **User Input** → Frontend validates and formats airport codes
2. **API Request** → Flask routes process single airport or multi-airport requests
3. **Airport Lookup** → OpenFlights database provides airport metadata and coordinates
4. **Weather Fetching** → Multi-source API calls with intelligent fallbacks:
   - NOAA (primary) → FAA ADDS → Test data
5. **Weather Processing** → METAR parsing, severity analysis, operational decisions
6. **AI Enhancement** → LLM-powered briefings and plain English summaries
7. **Response Assembly** → Structured JSON with airport info, weather, AI analysis
8. **Frontend Rendering** → Interactive maps, severity badges, operational recommendations

### Key Design Patterns

**Multi-Source Data Strategy**: Weather APIs have fallback hierarchy (NOAA → FAA → synthetic data) ensuring availability

**Operational Decision Engine**: Real-time analysis of visibility, ceiling, wind conditions to recommend alternates, delays, or route modifications

**AI Integration with Validation**: LLM outputs are verified against parsed METAR tokens to ensure accuracy; deterministic fallbacks prevent hallucination

**Modular Architecture**: Separate concerns between weather fetching, AI analysis, and operational decisions for maintainability

## Environment Variables

Required for full functionality:
```bash
DEEPSEEK_API_KEY=your-deepseek-api-key
GEMINI_API_KEY=your-gemini-api-key
CHECKWX_API_KEY=your-checkwx-api-key  # Optional
AVWX_API_KEY=your-avwx-api-key        # Optional
```

## Common Development Scenarios

### Adding a New Weather Source
1. Extend `WeatherAPIManager` in `weather_apis.py`
2. Add API configuration to `__init__` method
3. Implement fetch method following existing pattern with error handling
4. Update priority order in source selection logic

### Modifying METAR Parsing
- Core parsing logic in `tokenize_metar()` function in `ai_analysis.py`
- Deterministic fallback in `deterministic_summary()` 
- Weather phenomena definitions in `weather_apis.py` `_parse_weather_phenomena()`

### Enhancing Operational Decisions
- Main logic in `recommend_operational_actions()` in `aerolish_final.py`
- Modify trigger conditions for risk alerts and alternate recommendations
- Distance calculations use haversine formula for alternate airport suggestions

### Adding New Airport Data
- Primary source is OpenFlights database (automatic)
- Hardcoded fallbacks can be added to `hardcoded_airports` in `app.py`
- Indian airports specifically configured in `config.py`

### Customizing AI Analysis
- Prompt engineering in `ai_analysis.py` method `_generate_*` functions  
- Model selection logic in `_call_ai_service()` with DeepSeek → Gemini fallback
- Token validation prevents AI hallucination via `_verify_text_matches_tokens()`

## Frontend Integration Points

The frontend expects these JSON response structures:

**Single Airport**: `{icao, airport, weather: {metar}, ai_briefing, operational_decisions, timestamp}`

**Route Analysis**: `{route, analysis: {airports}, timeline, overall_conditions, operational_decisions, timestamp}`

Map markers use severity color coding: SEVERE (red), MODERATE (yellow), CLEAR (green), UNKNOWN (gray).

## Important Architectural Notes

- **No Database**: Application is stateless, relying on external APIs and in-memory caching
- **Weather Data Freshness**: METAR data typically updated hourly, cached for 5 minutes
- **Airport Coordinates**: Essential for mapping and alternate recommendations; sourced from OpenFlights
- **Operational Safety**: Risk thresholds are conservative (visibility < 3SM, ceiling < 1000ft, gusts > 30kt trigger decision support)
- **Multi-Language Support**: Airport names support international characters via OpenFlights database

## Testing Strategy

Focus testing on these critical paths:
- Weather API failover logic under network conditions
- METAR parsing accuracy with edge cases (variable winds, multiple weather phenomena)
- AI output validation and deterministic fallbacks
- Route analysis with mixed severity conditions
- Frontend map rendering with invalid coordinates
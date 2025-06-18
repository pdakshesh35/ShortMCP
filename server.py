from typing import Any
import httpx
from mcp.server.fastmcp import FastMCP

# Initialize FastMCP server
mcp = FastMCP("weather")

# Constants
NWS_API_BASE = "https://api.weather.gov"
USER_AGENT = "weather-app/1.0"

PROMPT_STRUCTURE_INSTRUCTIONS = """
Output the response as JSON in this exact structure:
    {{
    "1": {{ "script": "Scene 1 script here", "imagePrompt": "Scene 1 image description", "effect": "pan_left", "duration": 15 }},
    "2": {{ "script": "Scene 2 script here", "imagePrompt": "Scene 2 image description", "effect": "zoom_in", "duration": 12 }},
    ...,
    "metadata": {{ "title": "Insert catchy video title based on the content", "description": "Insert a short YouTube-style description summarizing the story in 1–2 lines with hashtags if relevant" }}
    }}
Each scene should:
    • Be 10–15 seconds long
    • Push the story forward in a fun, engaging way
    • Use visual metaphors or animated whiteboard/doodle-style scenes
    • Include motion effects like zoom_in, pan_right, fade_in, wobble, etc.
"""

async def make_nws_request(url: str) -> dict[str, Any] | None:
    """Make a request to the NWS API with proper error handling."""
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/geo+json"
    }
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, headers=headers, timeout=30.0)
            response.raise_for_status()
            return response.json()
        except Exception:
            return None

def format_alert(feature: dict) -> str:
    """Format an alert feature into a readable string."""
    props = feature["properties"]
    return f"""
Event: {props.get('event', 'Unknown')}
Area: {props.get('areaDesc', 'Unknown')}
Severity: {props.get('severity', 'Unknown')}
Description: {props.get('description', 'No description available')}
Instructions: {props.get('instruction', 'No specific instructions provided')}
"""

@mcp.tool()
async def get_alerts(state: str) -> str:
    """Get weather alerts for a US state.

    Args:
        state: Two-letter US state code (e.g. CA, NY)
    """
    url = f"{NWS_API_BASE}/alerts/active/area/{state}"
    data = await make_nws_request(url)

    if not data or "features" not in data:
        return "Unable to fetch alerts or no alerts found."

    if not data["features"]:
        return "No active alerts for this state."

    alerts = [format_alert(feature) for feature in data["features"]]
    return "\n---\n".join(alerts)

@mcp.tool()
async def get_forecast(latitude: float, longitude: float) -> str:
    """Get weather forecast for a location.

    Args:
        latitude: Latitude of the location
        longitude: Longitude of the location
    """
    # First get the forecast grid endpoint
    points_url = f"{NWS_API_BASE}/points/{latitude},{longitude}"
    points_data = await make_nws_request(points_url)

    if not points_data:
        return "Unable to fetch forecast data for this location."

    # Get the forecast URL from the points response
    forecast_url = points_data["properties"]["forecast"]
    forecast_data = await make_nws_request(forecast_url)

    if not forecast_data:
        return "Unable to fetch detailed forecast."

    # Format the periods into a readable forecast
    periods = forecast_data["properties"]["periods"]
    forecasts = []
    for period in periods[:5]:  # Only show next 5 periods
        forecast = f"""
{period['name']}:
Temperature: {period['temperature']}°{period['temperatureUnit']}
Wind: {period['windSpeed']} {period['windDirection']}
Forecast: {period['detailedForecast']}
"""
        forecasts.append(forecast)

    return "\n---\n".join(forecasts)

@mcp.prompt(
    "script-prompt",
    description="Prompt template that converts a raw news article into a multi-scene JSON script",
)
def news_script_prompt(article: str) -> str:
    """Build the structured prompt for script generation."""
    return (
        f"""
            Act as a viral content strategist and news scriptwriter for vertical video platforms like YouTube Shorts, Instagram Reels, TikTok, and Snapchat.
            Your task is to break down the following news story into a short-form, highly engaging 2-minute narration targeted at college students and young professionals (ages 18–30).
            Tone: Witty, informative, and lightly meme-style — like a confident, sarcastic best friend who knows her facts and isn’t afraid to drop a punchline.
            Voice: Female with strong personality. Include rhetorical hooks, Gen Z-friendly humor, and clever metaphors. Feel free to reference pop culture, TikTok trends, or modern slang in a tasteful way.
            News Style: Cover all types — breaking news, trending topics, weird facts, tech, social issues, etc.
            {PROMPT_STRUCTURE_INSTRUCTIONS}

            End the final scene with a strong call to action, like:
            “If you liked this, hit follow — you deserve better news.”
            Begin with this news story:
            {article}
        """
    )

@mcp.tool()
async def get_news(news: str) -> str:
    """.
    Get News into Divided multi scene
    Args:
        news : news content
    """
    return news_script_prompt(news)

@mcp.tool()
async def generate_text_to_speech(script:str) -> 


if __name__ == "__main__":
    # Initialize and run the server
    mcp.run(transport='stdio')
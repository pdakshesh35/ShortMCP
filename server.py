from typing import Any, Dict, Optional

import httpx
from mcp.server.fastmcp import FastMCP

# Initialize FastMCP server
mcp = FastMCP("news")

# Constants for the example weather tools
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


async def make_nws_request(url: str) -> Optional[Dict[str, Any]]:
    """Make a request to the NWS API with proper error handling."""
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/geo+json",
    }
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, headers=headers, timeout=30.0)
            response.raise_for_status()
            return response.json()
        except Exception:
            return None


def format_alert(feature: Dict[str, Any]) -> str:
    """Format an alert feature into a readable string."""
    props = feature["properties"]
    return (
        f"Event: {props.get('event', 'Unknown')}\n"
        f"Area: {props.get('areaDesc', 'Unknown')}\n"
        f"Severity: {props.get('severity', 'Unknown')}\n"
        f"Description: {props.get('description', 'No description available')}\n"
        f"Instructions: {props.get('instruction', 'No specific instructions provided')}"
    )


@mcp.tool()
async def get_alerts(state: str) -> str:
    """Get weather alerts for a US state."""
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
    """Get weather forecast for a location."""
    points_url = f"{NWS_API_BASE}/points/{latitude},{longitude}"
    points_data = await make_nws_request(points_url)

    if not points_data:
        return "Unable to fetch forecast data for this location."

    forecast_url = points_data["properties"]["forecast"]
    forecast_data = await make_nws_request(forecast_url)

    if not forecast_data:
        return "Unable to fetch detailed forecast."

    periods = forecast_data["properties"]["periods"]
    forecasts = []
    for period in periods[:5]:  # Only show next 5 periods
        forecast = (
            f"{period['name']}:\n"
            f"Temperature: {period['temperature']}°{period['temperatureUnit']}\n"
            f"Wind: {period['windSpeed']} {period['windDirection']}\n"
            f"Forecast: {period['detailedForecast']}"
        )
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
            "If you liked this, hit follow — you deserve better news."
            Begin with this news story:
            {article}
        """
    )


@mcp.tool()
async def get_news(news: str) -> str:
    """Divide a news story into a multi-scene JSON script."""
    return news_script_prompt(news)


@mcp.tool()
async def generate_image(prompt: str) -> str:
    """Placeholder for image generation."""
    # In a full implementation this would call an image generation service.
    return "image_placeholder.png"


@mcp.tool()
async def generate_text_to_speech(script: str) -> str:
    """Placeholder for text-to-speech generation."""
    # In a full implementation this would call a TTS service.
    return "tts_audio_placeholder.mp3"


@mcp.tool()
async def compile_video(scenes: Dict[str, Any]) -> str:
    """Placeholder for final video compilation."""
    # In a full implementation this would stitch images and audio together.
    return "vertical_video_placeholder.mp4"


if __name__ == "__main__":
    # Initialize and run the server
    mcp.run(transport="stdio")

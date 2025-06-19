from typing import Any, Dict, Optional

import json
import shutil

import os
import uuid
import asyncio
from openai import OpenAI
from runware import Runware, IImageInference
from video_generator import VideoGenerator

import httpx
from mcp.server.fastmcp import FastMCP

# Valid effects for each scene
ALLOWED_EFFECTS = {
    "zoom_in",
    "zoom_out",
    "pan_left",
    "pan_right",
    "pan_up",
    "pan_down",
}

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
    • Include motion effects like zoom_in, zoom_out, pan_left, pan_right, pan_up, or pan_down (use only these values)
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
    """Generate an image and save it locally.

    The Runware API is used to create the image based on ``prompt``. The
    resulting image is downloaded to the ``data`` directory and the local file
    path is returned so downstream tools can use it directly.
    """
    api_key = os.getenv("RUNWARE_API_KEY")
    if not api_key:
        raise RuntimeError("RUNWARE_API_KEY environment variable is not set")

    client = Runware(api_key=api_key)
    await client.connect()

    request = IImageInference(
        positivePrompt=prompt,
        taskUUID=str(uuid.uuid4()),
        model="runware:100@1",
        numberResults=1,
        height=2048,
        width=1152,
    )
    images = await client.imageInference(requestImage=request)
    if not images or len(images) == 0:
        raise RuntimeError("No image generated")

    url = images[0].imageURL

    os.makedirs("data", exist_ok=True)
    local_path = os.path.join("data", f"img_{uuid.uuid4()}.jpg")

    async with httpx.AsyncClient() as http:
        try:
            resp = await http.get(url, timeout=60.0)
            resp.raise_for_status()
        except Exception as exc:
            raise RuntimeError("Failed to download generated image") from exc

    with open(local_path, "wb") as f:
        f.write(resp.content)

    return local_path


@mcp.tool()
async def generate_text_to_speech(script: str) -> str:
    """Convert script text to speech using OpenAI TTS and return the file path."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY environment variable is not set")

    client = OpenAI(api_key=api_key)
    os.makedirs("data", exist_ok=True)
    file_path = os.path.join("data", f"tts_{uuid.uuid4()}.mp3")

    response = await asyncio.to_thread(
        lambda: client.audio.speech.create(
            model="tts-1",
            voice="nova",
            input=script,
        )
    )
    await asyncio.to_thread(response.stream_to_file, file_path)
    return file_path


@mcp.tool()
async def compile_video(scenes_json: str | Dict[str, Any]) -> str:
    """Stitch scenes with audio and images into a vertical video.

    Parameters
    ----------
    scenes_json: str | dict
        JSON string or already-parsed dictionary describing the scenes and
        optional metadata. Scenes must be provided under a ``"scenes"`` key
        with numeric identifiers.

        Each scene dictionary is expected to contain the keys:
        ``script`` (caption text), ``audioPath`` (voiceover file path),
        ``imagePath`` (URL or local path to the background image),
        ``duration`` (length in seconds) and ``effect``. The ``effect`` must
        be one of :data:`ALLOWED_EFFECTS`.
    """
    print("Parsing JSON for scenes...", flush=True)
    if isinstance(scenes_json, dict):
        data = scenes_json
    else:
        try:
            data = json.loads(scenes_json)
        except json.JSONDecodeError as exc:
            raise RuntimeError("Invalid JSON passed to compile_video") from exc

    scenes = data.get("scenes", data)

    # create a unique directory for this news video
    base_dir = os.path.join("data", f"news_{uuid.uuid4()}")
    os.makedirs(base_dir, exist_ok=True)
    output_path = os.path.join(base_dir, "video.mp4")

    print("Preparing scene assets...", flush=True)
    async with httpx.AsyncClient() as client:
        for key, scene in scenes.items():
            if not str(key).isdigit():
                continue
            print(f"Processing scene {key}...", flush=True)
            effect = scene.get("effect")
            if effect not in ALLOWED_EFFECTS:
                raise RuntimeError(f"Invalid effect '{effect}' in scene {key}")

            # Copy or download audio
            audio_src = scene.get("audioPath")
            if not audio_src:
                raise RuntimeError(f"Missing audioPath for scene {key}")
            audio_ext = os.path.splitext(str(audio_src))[1] or ".mp3"
            audio_dest = os.path.join(base_dir, f"audio_{key}{audio_ext}")
            if isinstance(audio_src, str) and audio_src.startswith(("http://", "https://")):
                try:
                    resp = await client.get(audio_src, timeout=60.0)
                    resp.raise_for_status()
                    with open(audio_dest, "wb") as f:
                        f.write(resp.content)
                except Exception:
                    raise RuntimeError(f"Failed to download audio for scene {key}")
            else:
                try:
                    shutil.copy(audio_src, audio_dest)
                except Exception as exc:
                    raise RuntimeError(f"Failed to copy audio for scene {key}") from exc
            scene["audioPath"] = audio_dest

            # Copy or download image
            image_src = scene.get("imagePath")
            if not image_src:
                raise RuntimeError(f"Missing imagePath for scene {key}")
            image_ext = os.path.splitext(str(image_src))[1] or ".jpg"
            image_dest = os.path.join(base_dir, f"image_{key}{image_ext}")
            if isinstance(image_src, str) and image_src.startswith(("http://", "https://")):
                try:
                    resp = await client.get(image_src, timeout=60.0)
                    resp.raise_for_status()
                    with open(image_dest, "wb") as f:
                        f.write(resp.content)
                except Exception:
                    raise RuntimeError(f"Failed to download image for scene {key}")
            else:
                try:
                    shutil.copy(image_src, image_dest)
                except Exception as exc:
                    raise RuntimeError(f"Failed to copy image for scene {key}") from exc
            scene["imagePath"] = image_dest

    print("Stitching video...", flush=True)
    generator = VideoGenerator(width=1080, height=1920)
    await asyncio.to_thread(generator.create_final_video, scenes, output_path)
    print(f"Video saved to {output_path}", flush=True)
    return output_path


if __name__ == "__main__":
    # Initialize and run the server
    mcp.run(transport="stdio")

from typing import Any, Dict, Optional
import concurrent.futures

import base64

import json

import os
import uuid
import asyncio
from openai import OpenAI
from runware import Runware, IImageInference
from video_generator import VideoGenerator
from starlette.responses import Response

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

# Background music files per niche
# Only "news" has a default track but new niches can be added
BG_MUSIC_MAP = {
    "news": os.getenv("NEWS_BG_MUSIC_PATH", os.path.join("data/bg_music", "news-bg-music.mp3")),
}

# Initialize FastMCP server
mcp = FastMCP("news")

RUNWARE_MODEL_ID = os.getenv("RUNWARE_MODEL_ID", "runware:97@3")
# Thread pool executor for heavy video generation tasks
THREAD_POOL = concurrent.futures.ThreadPoolExecutor(
    max_workers=int(os.getenv("VIDEO_WORKERS", "4"))
)

# Constants for the example weather tools
NWS_API_BASE = "https://api.weather.gov"
USER_AGENT = "weather-app/1.0"

PROMPT_STRUCTURE_INSTRUCTIONS = """
Output the response as JSON in this exact structure:
    {
        "niche": "{niche}",
        "scenes": {
            "1": { "script": "Scene 1 script here", "imagePrompt": "Scene 1 image description", "effect": "pan_left", "duration": 15, "instruction": "Deliver this scene in a confident, slightly sassy tone. Emphasize sarcasm on [specific line if needed], keep pace steady, and engage like you're dropping tea at brunch. Maintain same female narrator voice throughout all scenes." },
            "2": { "script": "Scene 2 script here", "imagePrompt": "Scene 2 image description", "effect": "zoom_in", "duration": 12, "instruction": "Same voice and energy as Scene 1. Add a playful smirk in your tone when mentioning [insert phrase]. Keep it energetic, punchy, and smart." },
            ...,
            "metadata": { "title": "Insert catchy video title based on the content", "description": "Insert a short YouTube-style description summarizing the story in 1–2 lines with hashtags if relevant" }
        }
    }
Put all scenes under the "scenes" key and include the niche value at the top level.
Each scene should:
    • Be 10–15 seconds long
    • Push the story forward in a fun, engaging way
    • Use visual metaphors or animated whiteboard/doodle-style scenes
    • The effect must be exactly one of: zoom_in, zoom_out, pan_left, pan_right, pan_up, pan_down

Key Notes for the instruction Field:
   - Tailored to each scene’s tone and pacing.
   - Includes emotional direction (e.g., sarcasm, surprise, playfulness).
   - Ensures narrator consistency across the video.
   - Optimized for AI voice tools like openai.


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
    description="Prompt template that converts raw text into a multi-scene JSON script",
)
def build_script_prompt(text: str, niche: str) -> str:
    """Build the structured prompt for script generation."""
    return (
        f"""
            Act as a viral content strategist and scriptwriter for vertical video platforms like YouTube Shorts, Instagram Reels, TikTok, and Snapchat.
            The content niche is: {niche}.
            Break down the following text into a short-form, highly engaging narration targeted at college students and young professionals (ages 18–30).
            Tone: Witty, informative, and lightly meme-style — like a confident, sarcastic best friend who knows her facts and isn’t afraid to drop a punchline.
            Voice: Female with strong personality. Include rhetorical hooks, Gen Z-friendly humor, and clever metaphors. Feel free to reference pop culture, TikTok trends, or modern slang in a tasteful way.
            {PROMPT_STRUCTURE_INSTRUCTIONS}

            End the final scene with a strong call to action, like:
            "If you liked this, hit follow — you deserve better news."
            Begin with this text:
            {text}
        """
    )


@mcp.tool()
async def generate_prompt(text: str, niche: str) -> str:
    """Use OpenAI to convert raw ``text`` into a multi-scene JSON script."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY environment variable is not set")

    client = OpenAI(api_key=api_key)
    prompt = build_script_prompt(text, niche)
    print("Requesting script from OpenAI...", flush=True)
    response = await asyncio.to_thread(
        client.chat.completions.create,
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
    )
    return response.choices[0].message.content.strip()


async def _generate_image(
    prompt: str,
    dest: str,
    negative_prompt: str | None = None,
    model_id: str | None = None,
) -> str:
    """Generate an image with Runware and save it to ``dest``.

    Parameters
    ----------
    prompt: str
        Positive prompt text describing the desired image.
    dest: str
        File path where the downloaded image should be saved.
    negative_prompt: str | None, optional
        Negative prompt text to steer the generator away from unwanted
        elements. If ``None``, no negative prompt is sent.
    model_id: str | None, optional
        ID of the Runware model to use. When ``None`` the environment
        variable ``RUNWARE_MODEL_ID`` is used.
    """
    api_key = os.getenv("RUNWARE_API_KEY")
    if not api_key:
        raise RuntimeError("RUNWARE_API_KEY environment variable is not set")

    client = Runware(api_key=api_key)
    await client.connect()

    request = IImageInference(
        positivePrompt=prompt,
        taskUUID=str(uuid.uuid4()),
        model=model_id or RUNWARE_MODEL_ID,
        numberResults=1,
        height=2048,
        width=1152,
        negativePrompt=negative_prompt,
    )
    images = await client.imageInference(requestImage=request)
    if not images or len(images) == 0:
        raise RuntimeError("No image generated")

    url = images[0].imageURL

    async with httpx.AsyncClient() as http:
        try:
            resp = await http.get(url, timeout=60.0)
            resp.raise_for_status()
        except Exception as exc:
            raise RuntimeError("Failed to download generated image") from exc
    with open(dest, "wb") as f:
        f.write(resp.content)
    return dest


async def _generate_tts(script: str, instruction: str, dest: str) -> str:
    """Convert ``script`` text to speech using OpenAI TTS and save it to ``dest``."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY environment variable is not set")

    client = OpenAI(api_key=api_key)

    response = await asyncio.to_thread(
        lambda: client.audio.speech.create(
            model="gpt-4o-mini-tts",
            voice="nova",
            input=script,
            instructions=instruction
        )
    )
    await asyncio.to_thread(response.stream_to_file, dest)
    return dest


async def generate_video(scenes_json: str | Dict[str, Any], niche: str) -> str:
    """Generate all assets and stitch them into a final MP4 video.

    Parameters
    ----------
    scenes_json: str | dict
        JSON string or already-parsed dictionary describing the scenes.
        Scenes must be provided under a ``"scenes"`` key with numeric
        identifiers. Each scene should include ``script``, ``imagePrompt``,
        ``duration`` and ``effect``. ``effect`` must be one of
        :data:`ALLOWED_EFFECTS`. Optionally add ``negativeImagePrompt`` and
        ``runwareModelId`` to control image generation.
    niche: str
        Text label for the type of content (e.g. "news", "sports"). Used only
        to organize temporary assets.
    """
    try:
        print("Parsing JSON for scenes...", flush=True)
        if isinstance(scenes_json, dict):
            data = scenes_json
        else:
            try:
                data = json.loads(scenes_json)
            except json.JSONDecodeError as exc:
                raise RuntimeError("Invalid JSON passed to generate_video") from exc

        scenes = data.get("scenes", data)

        safe_niche = ''.join(c if c.isalnum() or c in '-_' else '_' for c in niche.lower())
        base_dir = os.path.join("data", f"{safe_niche}_{uuid.uuid4()}")
        os.makedirs(base_dir, exist_ok=True)
        output_path = os.path.join(base_dir, "video.mp4")

        print("Generating scene assets...", flush=True)
        for key, scene in scenes.items():
            if not str(key).isdigit():
                continue
            print(f"Processing scene {key}...", flush=True)
            effect = scene.get("effect")
            if effect not in ALLOWED_EFFECTS:
                raise RuntimeError(f"Invalid effect '{effect}' in scene {key}")
            script = scene.get("script")
            prompt = scene.get("imagePrompt", script)
            negative = scene.get("negativeImagePrompt")
            model_id = scene.get("runwareModelId")
            instruction = scene.get("instruction")

            audio_dest = os.path.join(base_dir, f"audio_{key}.mp3")
            image_dest = os.path.join(base_dir, f"image_{key}.jpg")
            await _generate_tts(script, instruction, audio_dest)
            await _generate_image(prompt, image_dest, negative, model_id)
            scene["audioPath"] = audio_dest
            scene["imagePath"] = image_dest

        print("Stitching video...", flush=True)
        generator = VideoGenerator(width=1080, height=1920)
        bg_music = BG_MUSIC_MAP.get(niche.lower())
        await asyncio.to_thread(
            generator.create_final_video,
            scenes,
            output_path,
            bg_music,
        )
        with open(output_path, "rb") as f:
            video_bytes = f.read()
        print("Cleaning up temporary files...", flush=True)
        for fname in os.listdir(base_dir):
            path = os.path.join(base_dir, fname)
            try:
                os.remove(path)
            except Exception:
                pass
        try:
            os.rmdir(base_dir)
        except Exception:
            pass
        print(f"Video saved to {output_path} and folder cleaned", flush=True)
        return base64.b64encode(video_bytes).decode("ascii")
    except Exception as exc:
        print(f"Error during video generation: {exc}", flush=True)
        return f"ERROR: {exc}"


app = mcp.sse_app()


async def generate_video_threaded(scenes_json: Dict[str, Any], niche: str) -> str:
    """Run ``generate_video`` in a separate thread to avoid blocking the event loop."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        THREAD_POOL, lambda: asyncio.run(generate_video(scenes_json, niche))
    )


async def generate_video_api(request):
    """HTTP API wrapper for :func:`generate_video`.

    Expects JSON with ``niche`` and ``scenes`` keys and returns the final
    video file. If an error occurs a JSON object with ``error`` is returned
    instead.
    """
    try:
        payload: Dict[str, Any] = await request.json()
    except Exception:
        return Response(
            json.dumps({"error": "Invalid JSON payload"}),
            media_type="application/json",
            status_code=400,
        )
    niche = payload.get("niche", "news")
    scenes = payload.get("scenes")
    if scenes is None:
        return Response(
            json.dumps({"error": "Missing 'scenes' field"}),
            media_type="application/json",
            status_code=400,
        )
    result = await generate_video_threaded({"scenes": scenes}, niche)
    if isinstance(result, str) and result.startswith("ERROR"):
        return Response(
            json.dumps({"error": result}),
            media_type="application/json",
            status_code=500,
        )
    video_bytes = base64.b64decode(result)
    return Response(video_bytes, media_type="video/mp4")


app.add_route("/api/generate_video", generate_video_api, methods=["POST"])


if __name__ == "__main__":
    # Run the server with SSE and a generous keep-alive timeout so long
    # video generation tasks don't time out.
    import uvicorn

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=int(os.environ.get("PORT", mcp.settings.port)),
        log_level=mcp.settings.log_level.lower(),
        timeout_keep_alive=1800
    )

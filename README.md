# ShortMCP

This repository demonstrates a basic [MCP](https://github.com/manycoredai/mcp) server that exposes a few placeholder tools for generating vertical news videos.  The tools currently return simple placeholder values but show the structure for integrating weather data, image generation, text-to-speech and video compilation.

Run the server with SSE transport:

```bash
python server.py
```

Make sure the environment variables `OPENAI_API_KEY` and `RUNWARE_API_KEY` are
set to enable image and audio generation. Video stitching requires `ffmpeg` to
be installed along with the Python packages `moviepy`, `Pillow` and `numpy`.

The `generate_image` tool returns the path to a downloaded JPEG created from the
Runware API. Likewise, `generate_text_to_speech` produces an MP3 file and
returns its path. Use these paths as the `imagePath` and `audioPath` values when
calling `compile_video`.

The `compile_video` tool accepts a JSON string or parsed dictionary describing the
scenes and optional metadata for the final video. Each scene dictionary should
include the following keys:

- `script` – text displayed as dynamic subtitles
- `audioPath` – path to the voiceover MP3 file
- `imagePath` – URL or local path to the scene image
- `duration` – approximate length of the scene in seconds
- `effect` – one of `zoom_in`, `zoom_out`, `pan_left`, `pan_right`,
  `pan_up` or `pan_down`

The scenes must be nested under a `"scenes"` key with numeric identifiers as
shown below:

```json
{
  "scenes": {
    "1": {
      "effect": "zoom_in",
      "script": "Scene one script",
      "duration": 15,
      "audioPath": "data/tts_123.mp3",
      "imagePath": "https://example.com/image1.jpg"
    },
    "2": {
      "effect": "pan_left",
      "script": "Scene two script",
      "duration": 12,
      "audioPath": "data/tts_456.mp3",
      "imagePath": "https://example.com/image2.jpg"
    }
  }
}
```

Remote image URLs are downloaded automatically before stitching the final video.

When `compile_video` runs, it creates a unique folder under `data/` for the
current news item.  Scene audio and image files are moved (or downloaded) into
this folder with sequential names like `audio_1.mp3` and `image_1.jpg`.  After
the video is stitched, these temporary files are removed so the folder only
contains `video.mp4`.  Scenes are stitched in numeric order starting from 1.

The server exposes tools that can be called from a compatible MCP client such as Claude Desktop. The server uses Server-Sent Events (SSE) so clients receive progress updates while long running operations execute.

## Docker

Build the container and run it on port `8000`:

```bash
docker build -t shortmcp .
docker run -p 8000:8000 -e OPENAI_API_KEY=... -e RUNWARE_API_KEY=... shortmcp
```

The container executes `run.sh`, which simply launches `python server.py`.

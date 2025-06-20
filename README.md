# ShortMCP

This repository demonstrates a basic [MCP](https://github.com/manycoredai/mcp) server that can turn a news article into a short-form vertical video.

The server exposes two high level tools:

- `generate_prompt` – converts a raw news article into JSON describing each scene.
- `generate_video` – uses that JSON to create images and voiceovers, stitches the scenes together, and returns the final video encoded with base64.

Run the server with SSE transport:

```bash
python server.py
```

Make sure the environment variables `OPENAI_API_KEY` and `RUNWARE_API_KEY` are
set to enable image and audio generation. Video stitching requires `ffmpeg` to
be installed along with the Python packages `moviepy`, `Pillow` and `numpy`.

`generate_video` expects a JSON string describing the scenes. Each scene must
include `script`, `imagePrompt`, `duration` and `effect` (one of
`zoom_in`, `zoom_out`, `pan_left`, `pan_right`, `pan_up` or `pan_down`).

The scenes must be nested under a `"scenes"` key with numeric identifiers as
shown below:

```json
{
  "scenes": {
    "1": {
      "effect": "zoom_in",
      "script": "Scene one script",
      "imagePrompt": "Description for scene one",
      "duration": 15
    },
    "2": {
      "effect": "pan_left",
      "script": "Scene two script",
      "imagePrompt": "Description for scene two",
      "duration": 12
    }
  }
}
```

`generate_video` downloads images and creates voiceovers automatically. It
stores all temporary files in a unique folder and removes them once the video is
stitched so only `video.mp4` remains. Scenes are stitched sequentially starting
from 1.

The server exposes tools that can be called from a compatible MCP client such as Claude Desktop. The server uses Server-Sent Events (SSE) so clients receive progress updates while long running operations execute.

## Docker

Build the container and run it on port `8000`:

```bash
docker build -t shortmcp .
docker run -p 8000:8000 -e OPENAI_API_KEY=... -e RUNWARE_API_KEY=... shortmcp
```

The container executes `run.sh`, which simply launches `python server.py`.

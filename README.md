# ShortMCP

This repository demonstrates a basic [MCP](https://github.com/manycoredai/mcp) server that can turn any short piece of text into a vertical video. The content can be from **any niche** such as news, sports, tech, lifestyle or entertainment.

The server exposes two high level tools:

- `generate_prompt` – converts raw text into JSON describing each scene. It expects a `niche` argument describing the topic area ("news", "tech", "sports", etc.).
- `generate_video` – takes that JSON and a `niche` argument, creates the images and voiceovers, stitches the scenes together, and returns the final video encoded with base64.

Run the server with SSE transport:

```bash
python server.py
```

Make sure the environment variables `OPENAI_API_KEY` and `RUNWARE_API_KEY` are
set to enable image and audio generation. Video stitching requires `ffmpeg` to
be installed along with the Python packages `moviepy`, `Pillow` and `numpy`.

`generate_video` expects two arguments: a JSON string describing the scenes and a
`niche` string. Each scene must include `script`, `imagePrompt`, `duration` and `effect` (one of
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

The server exposes tools that can be called from a compatible MCP client such as Claude Desktop. The server uses Server-Sent Events (SSE) with an extended keep-alive timeout so clients receive progress updates during long running operations without timing out.

### Calling via HTTP

`generate_video` can also be used as a simple API. Send the JSON scenes to
`/api/generate_video` and the server will respond with the final MP4 file.

Example using `curl`:

```bash
curl -X POST http://localhost:8000/api/generate_video \
  -H "Content-Type: application/json" \
  -d '{"niche":"news","scenes":{...}}' \
  --output video.mp4
```

The payload format matches the structure described above.

## Docker

Build the container and run it on port `8000`:

```bash
docker build -t shortmcp .
docker run -p 8000:8000 -e OPENAI_API_KEY=... -e RUNWARE_API_KEY=... shortmcp
```

The container executes `run.sh`, which simply launches `python server.py`.

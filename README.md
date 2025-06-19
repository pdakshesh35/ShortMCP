# ShortMCP

This repository demonstrates a basic [MCP](https://github.com/manycoredai/mcp) server that exposes a few placeholder tools for generating vertical news videos.  The tools currently return simple placeholder values but show the structure for integrating weather data, image generation, text-to-speech and video compilation.

Run the server with:

```bash
python server.py
```

Make sure the environment variables `OPENAI_API_KEY` and `RUNWARE_API_KEY` are
set to enable image and audio generation. Video stitching requires `ffmpeg` to
be installed along with the Python packages `moviepy`, `Pillow` and `numpy`.

The `compile_video` tool accepts a JSON string or parsed dictionary describing the scenes and
optional metadata for the final video. Each scene must include an `effect`
value describing the pan or zoom animation. Allowed values are `zoom_in`,
`zoom_out`, `pan_left`, `pan_right`, `pan_up` and `pan_down`. The scenes
should be nested under a `"scenes"` key with numeric identifiers as shown
below:

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

The server exposes tools that can be called from a compatible MCP client such as Claude Desktop.

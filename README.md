# ShortMCP

This repository demonstrates a basic [MCP](https://github.com/manycoredai/mcp) server that exposes a few placeholder tools for generating vertical news videos.  The tools currently return simple placeholder values but show the structure for integrating weather data, image generation, text-to-speech and video compilation.

Run the server with:

```bash
python server.py
```

Make sure the environment variables `OPENAI_API_KEY` and `RUNWARE_API_KEY` are
set to enable image and audio generation. Video stitching requires `ffmpeg` to
be installed along with the Python packages `moviepy`, `Pillow` and `numpy`.

The server exposes tools that can be called from a compatible MCP client such as Claude Desktop.

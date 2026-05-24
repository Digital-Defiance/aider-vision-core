
Install the engine package, then run the CLI or HTTP server.

{% include install.md %}

```bash
# Change directory into your git workspace
cd /path/to/your/project

# CLI
aider-vision-core --model sonnet --api-key anthropic=<key>

# Or headless HTTP API (from repo root)
aider-vision-core-serve --workspace /path/to/your/project
```

For the **Aider Vision** desktop app, use [aider-vision.digitaldefiance.org](https://aider-vision.digitaldefiance.org/) — it talks to this engine over HTTP.

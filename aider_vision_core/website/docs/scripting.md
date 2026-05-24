---
parent: More info
nav_order: 400
description: CLI scripting, Python API, and aider-vision-core-serve HTTP API.
---

# Scripting & headless API

{% include vision-notice.md %}

## HTTP API (Vision Core)

Run the local server for [Aider Vision](https://aider-vision.digitaldefiance.org/) or other clients:

```bash
aider-vision-core-serve --workspace /path/to/git/repo
# default http://127.0.0.1:8741 — see aider_vision_core/http_api.py
```

Sessions, streaming (SSE), and auth are implemented in the Python package; this site does not duplicate the OpenAPI spec.

## Command line & Python

You can script the engine via the command line or Python (same as upstream Aider, binary `aider-vision-core`).

## Command line

Aider takes a `--message` argument, where you can give it a natural language instruction.
It will do that one thing, apply the edits to the files and then exit.
So you could do:

```bash
aider-vision-core --message "make a script that prints hello" hello.js
```

Or you can write simple shell scripts to apply the same instruction to many files:

```bash
for FILE in *.py ; do
    aider-vision-core --message "add descriptive docstrings to all the functions" $FILE
done
```

Use `aider-vision-core --help` to see all the 
[command line options](/docs/config/options.html),
but these are useful for scripting:

```
--stream, --no-stream
                      Enable/disable streaming responses (default: True) [env var:
                      AIDER_STREAM]
--message COMMAND, --msg COMMAND, -m COMMAND
                      Specify a single message to send GPT, process reply then exit
                      (disables chat mode) [env var: AIDER_MESSAGE]
--message-file MESSAGE_FILE, -f MESSAGE_FILE
                      Specify a file containing the message to send GPT, process reply,
                      then exit (disables chat mode) [env var: AIDER_MESSAGE_FILE]
--yes                 Always say yes to every confirmation [env var: AIDER_YES]
--auto-commits, --no-auto-commits
                      Enable/disable auto commit of GPT changes (default: True) [env var:
                      AIDER_AUTO_COMMITS]
--dirty-commits, --no-dirty-commits
                      Enable/disable commits when repo is found dirty (default: True) [env
                      var: AIDER_DIRTY_COMMITS]
--dry-run, --no-dry-run
                      Perform a dry run without modifying files (default: False) [env var:
                      AIDER_DRY_RUN]
--commit              Commit all pending changes with a suitable commit message, then exit
                      [env var: AIDER_COMMIT]
```


## Python

You can also script aider from python:

```python
from aider_vision_core.coders import Coder
from aider_vision_core.models import Model

# This is a list of files to add to the chat
fnames = ["greeting.py"]

model = Model("gpt-4-turbo")

# Create a coder object
coder = Coder.create(main_model=model, fnames=fnames)

# This will execute one instruction on those files and then return
coder.run("make a script that prints hello world")

# Send another instruction
coder.run("make it say goodbye")

# You can run in-chat "/" commands too
coder.run("/tokens")

```

See the
[Coder.create() and Coder.__init__() methods](https://github.com/Aider-AI/aider/blob/main/aider/coders/base_coder.py)
for all the supported arguments.

It can also be helpful to set the equivalent of `--yes` by doing this:

```python
from aider_vision_core.io import InputOutput
io = InputOutput(yes=True)
# ...
coder = Coder.create(model=model, fnames=fnames, io=io)
```

{: .note }
The python scripting API is not officially supported or documented,
and could change in future releases without providing backwards compatibility.

#!/bin/bash

# exit when any command fails
set -e

if [ -z "$1" ]; then
  ARG=-r
else
  ARG=$1
fi

if [ "$ARG" != "--check" ]; then
  tail -1000 ~/.aider/analytics.jsonl > aider_vision_core/website/assets/sample-analytics.jsonl
  cog -r aider_vision_core/website/docs/faq.md
fi

# README.md before index.md, because index.md uses cog to include README.md
cog $ARG \
    README.md \
    aider_vision_core/website/index.html \
    aider_vision_core/website/HISTORY.md \
    aider_vision_core/website/docs/usage/commands.md \
    aider_vision_core/website/docs/languages.md \
    aider_vision_core/website/docs/config/dotenv.md \
    aider_vision_core/website/docs/config/options.md \
    aider_vision_core/website/docs/config/aider_conf.md \
    aider_vision_core/website/docs/config/adv-model-settings.md \
    aider_vision_core/website/docs/config/model-aliases.md \
    aider_vision_core/website/docs/leaderboards/index.md \
    aider_vision_core/website/docs/leaderboards/edit.md \
    aider_vision_core/website/docs/leaderboards/refactor.md \
    aider_vision_core/website/docs/llms/other.md \
    aider_vision_core/website/docs/more/infinite-output.md \
    aider_vision_core/website/docs/legal/privacy.md

---
nav_exclude: true
---

# Aider Vision Core documentation

{% include vision-notice.md %}

Documentation for the **headless engine** package (`aider-vision-core`). For the desktop app, see [Aider Vision](https://aider-vision.digitaldefiance.org/). For upstream tutorials and leaderboards, see [aider.chat/docs](https://aider.chat/docs/).

## Start here

- [Installation](/docs/install.html) — `pip install aider-vision-core`, `aider-vision-core-serve`
- [Scripting](/docs/scripting.html) — CLI scripting and HTTP API for headless clients
- [Git](/docs/git.html) — commits, undo, submodule workspaces
- [Configuration](/docs/config.html) — models, keys, options

## Fork vs upstream

| Topic | Here | Upstream |
|-------|------|----------|
| HTTP API / Vision serve | [Scripting](/docs/scripting.html) | — |
| Submodule monorepos | [Git](/docs/git.html) | basic git docs |
| LLMs, repomap, usage | mirrored docs | [aider.chat/docs](https://aider.chat/docs/) |

<div class="toc">
{% assign pages_list = site.html_pages | sort: "nav_order" %}

<ul>
{% for page in pages_list %}
  {% if page.title and page.url != "/" and page.parent == nil and page.nav_exclude != true %}
    <li>
      <a href="{{ page.url | absolute_url }}">{{ page.title }}</a>{% if page.description %} <span style="font-size: 0.9em; font-style: italic;">— {{ page.description }}</span>{% endif %}

      {% assign children = site.html_pages | where: "parent", page.title | sort: "nav_order" %}
      {% if children.size > 0 %}
        <ul>
        {% for child in children %}
          {% if child.title %}
            <li>
              <a href="{{ child.url | absolute_url }}">{{ child.title }}</a>{% if child.description %} <span style="font-size: 0.9em; font-style: italic;">— {{ child.description }}</span>{% endif %}

              {% assign grandchildren = site.html_pages | where: "parent", child.title | sort: "nav_order" %}
              {% if grandchildren.size > 0 %}
                <ul>
                {% for grandchild in grandchildren %}
                  {% if grandchild.title %}
                    <li>
                      <a href="{{ grandchild.url | absolute_url }}">{{ grandchild.title }}</a>{% if grandchild.description %} <span style="font-size: 0.9em; font-style: italic;">— {{ grandchild.description }}</span>{% endif %}
                    </li>
                  {% endif %}
                {% endfor %}
                </ul>
              {% endif %}
            </li>
          {% endif %}
        {% endfor %}
        </ul>
      {% endif %}
    </li>
  {% endif %}
{% endfor %}
</ul>
</div>

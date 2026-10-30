import os
import re

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def render_modular_template(template_name: str, context: dict) -> str:
    templates_dir = os.path.join(APP_DIR, "templates")
    main_file = os.path.join(templates_dir, template_name)
    with open(main_file, "r", encoding="utf-8") as f:
        html = f.read()

    def replace_include(match):
        sub_path = match.group(1).strip()
        sub_file = os.path.join(templates_dir, sub_path)
        if os.path.isfile(sub_file):
            with open(sub_file, "r", encoding="utf-8") as sf:
                return sf.read()
        return f"<!-- Missing: {sub_path} -->"

    pattern_include = re.compile(r"{%\s*include\s+['\"]([^'\"]+)['\"]\s*%}")
    html = pattern_include.sub(replace_include, html)

    for k, v in context.items():
        html = html.replace("{{ " + k + " }}", str(v))
        html = html.replace("{{" + k + "}}", str(v))
        html = html.replace("{{ " + k + "|safe }}", str(v))
        html = html.replace("{{" + k + "|safe}}", str(v))

    return html

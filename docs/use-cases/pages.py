#!/usr/bin/env python
"""Write the "Code" section of each use-case page from its script, one block for each cell.

    python docs/use-cases/pages.py

A script code/ucNN_*.py is divided into cells by lines that start with "# %%"; the rest of such a
line is the title of the cell. VS Code, PyCharm and Jupyter run a script with these lines cell by
cell. For each cell, the page ucNN.md gets the title and a code block that includes the lines of that
cell from the script (pymdownx.snippets, "file:first:last"). Thus the page always shows the code of
the script. Run this file again after a change to a script; build.py runs it at the end.
"""
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
HELPERS = ("prometheus_api", "chem_tools", "pyteck_tools")
CELL = re.compile(r"^# %%\s*(.*)$")


def cells(script):
    """[(title, first line, last line)] of the cells of a script; line numbers start at 1."""
    lines = script.read_text(encoding="utf-8").splitlines()
    starts = [i for i, line in enumerate(lines) if CELL.match(line)] + [len(lines)]
    found = []
    for start, end in zip(starts, starts[1:]):
        body = range(start + 1, end)
        used = [i for i in body if lines[i].strip()]
        if used:
            found.append((CELL.match(lines[start]).group(1), used[0] + 1, used[-1] + 1))
    return found


def code_section(script):
    text = script.read_text(encoding="utf-8")
    helpers = [h for h in HELPERS if re.search(rf"^from {h} import", text, re.M)]
    links = " and ".join(f"[{h}.py](code/{h}.py)" for h in helpers)
    out = ["## Code", "",
           f"[Download {script.name}](code/{script.name}). The script imports {links}; put "
           f"{'it' if len(helpers) == 1 else 'them'} in the same folder (see "
           "[Running the scripts](index.md#running-the-scripts)). A line `# %%` starts each cell, so an "
           "editor such as VS Code or Jupyter can run the script one cell at a time.", ""]
    for k, (title, first, last) in enumerate(cells(script), 1):
        out += [f"**{k}. {title}**", "", "```python", f'--8<-- "code/{script.name}:{first}:{last}"', "```", ""]
    return "\n".join(out)


def main():
    for script in sorted((HERE / "code").glob("uc[0-9][0-9]_*.py")):
        page = HERE / f"{script.name[:4]}.md"
        if not page.exists():
            print(f"no page for {script.name}")
            continue
        text = page.read_text(encoding="utf-8")
        new = re.sub(r"^## Code\n.*?(?=^## Result$)", lambda _: code_section(script) + "\n", text, flags=re.M | re.S)
        if new != text:
            page.write_text(new, encoding="utf-8")
            print(f"wrote  {page.name}: {len(cells(script))} cells")


if __name__ == "__main__":
    main()

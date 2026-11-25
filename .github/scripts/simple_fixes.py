"""Fixes that need no AI: add type="button" to a <button> that has an onClick but no type (SonarQube S9011).
Buttons without onClick are left alone, because they may be submit buttons."""
import pathlib
import re

TAG = re.compile(r"<button\b((?:[^>]|=>)*)>")
changed = 0
for f in pathlib.Path("frontend/src").rglob("*.tsx"):
    text = f.read_text()

    def fix(m):
        attrs = m.group(1)
        if re.search(r"\btype\s*=", attrs) or "onClick" not in attrs or "{..." in attrs:
            return m.group(0)
        return '<button type="button"' + attrs + ">"
    new = TAG.sub(fix, text)
    if new != text:
        f.write_text(new)
        changed += 1
print(f"simple fixes applied in {changed} files")

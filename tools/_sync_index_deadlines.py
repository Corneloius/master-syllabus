from pathlib import Path

repo = Path(__file__).resolve().parent.parent
key = '<table aria-label="Master Deadlines Table">'
m = (repo / "Master_Syllabus_Spring_2026.html").read_text(encoding="utf-8")
i = (repo / "index.html").read_text(encoding="utf-8")
b = m.split(key, 1)[1].split("</table>", 1)[0]
p0, p1 = i.split(key, 1)
p1_rest = p1.split("</table>", 1)
new_i = p0 + key + b + "</table>" + p1_rest[1]
(repo / "index.html").write_text(new_i, encoding="utf-8")
print("index.html Master Deadlines table replaced from Master_Syllabus_Spring_2026.html")

import pathlib
c = pathlib.Path("viewer.html").read_text(encoding="utf-8")
# 1585行目を探す
lines = c.split('\n')
line = lines[1584]  # 0-indexed
pathlib.Path("_hex.txt").write_text(repr(line[:80]), encoding="utf-8")

from pathlib import Path
p=Path('src/core/llm.py')
lines=p.read_text(encoding='utf-8').splitlines()
start=120
end=140
for i in range(start-1,end):
    print(f"{i+1}: {lines[i]}")

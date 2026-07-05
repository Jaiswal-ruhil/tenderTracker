from pathlib import Path
p=Path('src/core/llm.py')
lines=p.read_text(encoding='utf-8').splitlines()
start=80
end=180
for i in range(start-1,end):
    print(f"{i+1}: {lines[i]}")

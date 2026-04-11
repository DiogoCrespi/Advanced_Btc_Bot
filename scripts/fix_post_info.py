with open('MiroFish/backend/scripts/run_parallel_simulation.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

for i, line in enumerate(lines[650:870]):
    print(f"{i+651}: {line}", end='')

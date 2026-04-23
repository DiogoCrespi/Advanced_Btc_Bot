import subprocess
import base64
import os

files_to_sync = [
    'logic/tribunal.py',
    'logic/local_oracle.py',
    'logic/strategist_agent.py',
    'scout_bot.py',
    'multicore_master_bot.py'
]

password = "1597"
host = "diogo@100.86.220.116"
remote_dir = "Documents/Btc_bot"

for fpath in files_to_sync:
    if not os.path.exists(fpath):
        print(f"Skipping {fpath}, not found.")
        continue
    
    with open(fpath, 'rb') as f:
        b64_content = base64.b64encode(f.read()).decode('utf-8')
    
    temp_b64 = "temp_sync.b64"
    with open(temp_b64, 'w') as f:
        f.write(b64_content)
    
    # Use plink to write the file by piping stdin
    remote_path = f"{remote_dir}/{fpath}"
    dir_name = os.path.dirname(remote_path)
    
    print(f"Syncing {fpath}...")
    # Mkdir
    subprocess.run(f"plink -batch -ssh {host} -pw {password} \"mkdir -p {dir_name}\"", shell=True)
    
    # Pipe content
    cmd = f"type {temp_b64} | plink -batch -ssh {host} -pw {password} \"cat > {remote_path}.b64 && base64 -d < {remote_path}.b64 > {remote_path} && rm {remote_path}.b64\""
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    
    if result.returncode != 0:
        print(f"Error syncing {fpath}: {result.stderr}")
    else:
        print(f"Synced {fpath}")
    
    if os.path.exists(temp_b64):
        os.remove(temp_b64)

print("Sync complete.")

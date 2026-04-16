import paramiko
import getpass
import os

# SSH Connectivity
ssh_host = '100.86.220.116'
ssh_user = 'diogo'
ssh_pass = getpass.getpass(f"Password for {ssh_user}@{ssh_host}: ")

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(ssh_host, username=ssh_user, password=ssh_pass)

sftp = client.open_sftp()
base_remote_path = '/home/diogo/Documents/Btc_bot'
files_to_upload = [
    ('logic/local_oracle.py', f'{base_remote_path}/logic/local_oracle.py'),
]

for local, remote in files_to_upload:
    print(f"Uploading {local} to {remote}...")
    try:
        sftp.put(local, remote)
        print("Success!")
    except Exception as e:
        print(f"Failed to upload {local}: {e}")

sftp.close()
client.close()

import paramiko
import getpass

# SSH Connectivity
ssh_host = '100.86.220.116'
ssh_user = 'diogo'
ssh_pass = getpass.getpass(f"Password for {ssh_user}@{ssh_host}: ")

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(ssh_host, username=ssh_user, password=ssh_pass)

print("Executing restart command on remote server...")
cmd = 'cd /home/diogo/Documents/Btc_bot && docker compose up -d --build btc-master-bot && docker compose logs --tail=20 btc-master-bot'
stdin, stdout, stderr = client.exec_command(cmd)
print("STDOUT:", stdout.read().decode())
print("STDERR:", stderr.read().decode())
client.close()

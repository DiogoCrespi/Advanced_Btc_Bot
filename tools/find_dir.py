import paramiko
import getpass

# SSH Connectivity
ssh_host = '100.86.220.116'
ssh_user = 'diogo'
ssh_pass = getpass.getpass(f"Password for {ssh_user}@{ssh_host}: ")

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(ssh_host, username=ssh_user, password=ssh_pass)

print("Searching for Btc_bot directory on remote server...")
stdin, stdout, stderr = client.exec_command('find /home/diogo -type d -name "Btc_bot" 2>/dev/null')
print(stdout.read().decode())
client.close()

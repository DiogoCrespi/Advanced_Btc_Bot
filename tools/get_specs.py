import paramiko
import getpass

# SSH Connectivity
ssh_host = '100.86.220.116'
ssh_user = 'diogo'
ssh_pass = getpass.getpass(f"Password for {ssh_user}@{ssh_host}: ")

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(ssh_host, username=ssh_user, password=ssh_pass)

print("Retrieving system specs from remote server...")
cmd = "echo '---CPU---'; lscpu | grep 'Model name'; echo '---RAM---'; free -h; echo '---GPU---'; nvidia-smi || echo 'No GPU'; echo '---OLLAMA---'; systemctl status ollama --no-pager || echo 'Not running'"
stdin, stdout, stderr = client.exec_command(cmd)
print(stdout.read().decode())
err = stderr.read().decode()
if err: print("ERROR:", err)
client.close()

import paramiko
import getpass

# SSH Connectivity
ssh_host = '100.86.220.116'
ssh_user = 'diogo'
ssh_pass = getpass.getpass(f"Password for {ssh_user}@{ssh_host}: ")

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(ssh_host, username=ssh_user, password=ssh_pass)

# Environment variables to append (Use placeholders)
env_vars = """
GROQ_API_KEY=YOUR_GROQ_API_KEY_HERE
GEMINI_KEY_1=YOUR_GEMINI_KEY_1_HERE
GEMINI_KEY_2=YOUR_GEMINI_KEY_2_HERE
GEMINI_KEY_3=YOUR_GEMINI_KEY_3_HERE
GEMINI_KEY_4=YOUR_GEMINI_KEY_4_HERE
"""

print("Appending environment variables to remote .env...")
cmd = f"cat << 'EOF' >> /home/diogo/Documents/Btc_bot/.env\n{env_vars}\nEOF"
stdin, stdout, stderr = client.exec_command(cmd)
print("STDOUT:", stdout.read().decode())
print("STDERR:", stderr.read().decode())
client.close()

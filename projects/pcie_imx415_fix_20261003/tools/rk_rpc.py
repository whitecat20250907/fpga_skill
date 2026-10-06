"""Local SSH/SFTP helper; password is held in memory only."""
import getpass
import json
import sys
import paramiko

host = sys.argv[1] if len(sys.argv) > 1 else '192.168.43.213'
password = getpass.getpass('RK password: ')
client = None

def connect():
    global client
    if client is not None:
        client.close()
    client = paramiko.SSHClient()
    client.load_system_host_keys()
    client.set_missing_host_key_policy(paramiko.RejectPolicy())
    client.connect(host, username='linaro', password=password,
                   look_for_keys=False, allow_agent=False, timeout=8)

connect()
print('RPC_READY', flush=True)
for line in sys.stdin:
    try:
        req = json.loads(line)
        if req['op'] == 'reconnect':
            connect()
            result = {'connected': True}
        elif req['op'] == 'run':
            _, stdout, stderr = client.exec_command(req['command'], timeout=req.get('timeout', 60))
            result = {'stdout': stdout.read().decode(errors='replace'),
                      'stderr': stderr.read().decode(errors='replace'),
                      'exit': stdout.channel.recv_exit_status()}
        elif req['op'] in ('put', 'get'):
            with client.open_sftp() as sftp:
                if req['op'] == 'put':
                    sftp.put(req['local'], req['remote'])
                else:
                    sftp.get(req['remote'], req['local'])
            result = {'transferred': True}
        elif req['op'] == 'close':
            client.close()
            break
        else:
            raise ValueError('Unknown operation')
        print(json.dumps(result, ensure_ascii=False), flush=True)
    except Exception as error:
        print(json.dumps({'error': str(error)}, ensure_ascii=False), flush=True)

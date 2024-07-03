'''
@File    :  radar_client.py
@Time    :  2023/04/10 15:00:39
@Author  :  Zixin Shang @ thinszx
@Version :  None
@Contact :  zxshang@mail.ustc.edu.cn
@Desc    :  This file contains class to connect and control radar server.
@TODO    :  None
'''

import time
import socket
import paramiko

from paramiko.channel import ChannelStdinFile, ChannelFile, ChannelStderrFile

class RadarClient:
    """This class is used to connect and control radar server."""

    def __init__(self, radarip, username='root', password='', radarsshport=22, timeout=1) -> None:
        self.radarip = radarip
        self.radarsshport = radarsshport
        self.username = username
        self.password = password
        self.timeout = timeout
        
        self.ssh_client = None
        self.ssh_client = self.__get_ssh_connect()
        self.server_stdin = None
        self.server_stdout = None
        self.server_stderr = None

    
    def __del__(self):
        if self.ssh_client is not None:
            self.ssh_client.close()

    def __get_ssh_connect(self):
        if self.ssh_client is None:
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            client.connect(self.radarip, self.radarsshport, self.username, self.password, 
                           auth_timeout=self.timeout)
            self.ssh_client = client
        return self.ssh_client
    
    def send_command(self, command: str, waittime: float=0) -> tuple[ChannelStdinFile, ChannelFile, ChannelStderrFile]:
        """Send command to the radar server.

        Args:
            command (str): The command to be sent.
            waittime (float, optional): The time to wait after the command is sent. Defaults to -1.
        """
        ssh_client = self.__get_ssh_connect()
        stdin, stdout, stderr = ssh_client.exec_command(command)
        if waittime > 0:
            time.sleep(waittime)
        return stdin, stdout, stderr
    
    def start_server(self, protocol='tcp', port=18888, waittime=1.5) -> None:
        """Execute /mnt/ssd/ReadFileArmv3 -t server -trans tcp -host "0.0.0.0" -port 18888

        Args:
            protocol (str, optional): The protocol to be used for connection. Defaults to 'tcp'.
            port (int, optional): The port to be used for connection. Defaults to 18888.
            waittime (float, optional): The time to wait for the server to start. Defaults to 1.5.
        
        Raises:
            NotImplementedError: Invalid protocol.
            ValueError: Invalid port number.
            ChildProcessError: The command is not executed successfully.
        """
        if protocol not in ['tcp', 'udp']:
            raise NotImplementedError(f'Invalid protocol: {protocol}')
        # TODO
        if protocol == 'udp':
            raise NotImplementedError('UDP protocol is not supported yet.')
        if port > 65535 or port < 0:
            raise ValueError(f'Invalid port number: {port}')
        command = f'/mnt/ssd/ReadFileArmv3 -t server -trans {protocol} -host "0.0.0.0" -port {port}'

        try:
            ssh_client = self.__get_ssh_connect()
        except paramiko.AuthenticationException:
            raise paramiko.AuthenticationException(f'Authentication failed with the provided credentials: '
                            f'username-{self.username}, password-{self.password}') from None

        self.server_stdin, self.server_stdout, self.server_stderr = ssh_client.exec_command(command)
        if waittime > 0:
            time.sleep(waittime)
        # check if the command is executed successfully with unblocking call
        if self.server_stdout.channel.exit_status_ready() == True: # True means the command is executed but some error occurs
            raise ChildProcessError(' '.join(self.server_stderr.readlines()))
        
    def get_server_status(self, port=18888) -> bool:
        """Check if the server is running.

        Args:
            port (int, optional): The port to be used for connection. Defaults to 18888.

        Returns:
            bool: True if the server is running, False otherwise.
        """
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            return_value = s.connect_ex((self.radarip, port))
            if return_value == 0:
                return True
            else:
                return False
        
    def stop_server(self, port=18888, waittime=0.5) -> None:
        """Stop the server.

        Args:
            waittime (float, optional): The time to wait for the server to stop. Defaults to 0.5.

        Raises:
            ChildProcessError: The command is not executed successfully.
        """
        # check if the server is running
        if self.get_server_status(port) == False:
            return
        command = f"kill $(netstat -nlp | grep :{port} | awk '{{print $7}}' | cut -d'/' -f1)"
        ssh_client = self.__get_ssh_connect()
        _, stdout, stderr = ssh_client.exec_command(command)
        if waittime > 0:
            time.sleep(waittime)
        # check if the command is executed successfully with unblocking call
        # stderr.channel.exit_status == 0 means the command is executed and no error occurs
        if stdout.channel.exit_status_ready == True and stderr.channel.exit_status != 0:
            raise ChildProcessError(' '.join(stderr.readlines()))
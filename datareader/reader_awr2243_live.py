'''
@File    :  reader_awr2243_live.py
@Time    :  2023/04/06 15:42:09
@Author  :  Zixin Shang @ thinszx
@Version :  0.1
@Contact :  zxshang@mail.ustc.edu.cn
@Desc    :  This file contains the class for live AWR2243 data reader.
@TODO    :  None
'''


# from .reader_awr2243 import AWR2243Reader
import socket
import numpy as np

class LiveAWR2243Reader():
    """Live AWR2243 data reader class."""

    def __init__(self, server_dir, nloops, nsamples, serverip, serverport=18888, 
                 save_dir=None, save_period=1200, 
                 tx_enable=3, rx_enable=4, 
                 connect_timeout=5, query_timeout=2):
        """This function is used to initialize the class.

        Args:
            server_dir (str): The directory to save the received data. Defaults to None.
            nloops (int): The number of loops per frame.
            nsamples (int): The number of samples per loop.
            serverip (str): The IP address of the server.
            serverport (int, optional): The port of the server. Defaults to 18888.
            save_dir (str, optional): The directory to save the received data. Defaults to None.
                                        If None, the data will not be saved.
            save_period (int, optional): The period of saving frames. Defaults to 1200.
                                         Only valid when `save_dir` is not None.
            tx_enable (int, optional): The number of tx antennas. Defaults to 3.
            rx_enable (int, optional): The number of rx antennas. Defaults to 4.
            connect_timeout (int, optional): The timeout of connecting to the server. Defaults to 5.
            query_timeout (int, optional): The timeout of querying data from the server. Defaults to 2.

        @ TODO: enable saving received data to file

        NOTICE: Practically, we only use tcp as the transport protocol 
                with `./ReadFileArmv3 -t server -trans tcp -host "0.0.0.0" -port 18888` on server,
                and I don't want to test other protocols. If you want to
                them, code it yourself :\.
        """
        self.serverip = serverip
        self.serverport = serverport
        self.nloops = nloops
        self.nsamples = nsamples

        self.client = None
        self.server_dir = server_dir
        self.connect_timeout = connect_timeout
        self.query_timeout = query_timeout

        # calculate the expected data length
        self.nchip = 4
        self.nwave = 2
        int16_size = 2
        self.header_size = 32 # maybe timestamp
        self.tx_enable = tx_enable
        self.rx_enable = rx_enable
        self.nchirps_one_loop = self.tx_enable * self.nchip
        # rx_enable * devices is all the rx antennas receiving `nchirps_one_loop` which is chirps tx antennas send in one loop
        self.expected_data_length = nsamples * self.nchirps_one_loop * nloops * rx_enable * int16_size * self.nwave * self.nchip + self.header_size

        isrunning, errmsg = self.is_server_running(self.serverip, self.serverport, self.connect_timeout)
        if not isrunning:
            raise ConnectionError(errmsg)
        

    def nextframe(self) -> np.ndarray:
        """Send query to the client and retrive frame."""
        client = self.__get_socket(reconnect=False)
        client.sendall(b'n')
        recv_data = b''
        client.settimeout(self.query_timeout)
        while len(recv_data) < self.expected_data_length:
            try:
                packet = client.recv(self.expected_data_length - len(recv_data))
                if not packet:
                    is_server_running, errmsg = self.is_server_running(self.serverip, self.serverport, self.query_timeout)
                    if is_server_running == True:
                        return None
                recv_data += packet
            except socket.timeout:
                # if the server is running but no data coming, take this as the symbol of the end of the frame
                is_server_running, errmsg = self.is_server_running(self.serverip, self.serverport, self.query_timeout)
                if is_server_running and len(recv_data) == 0:
                    return None
                elif is_server_running and len(recv_data) != 0:
                    # if the server is not running, but we have received some data, raise an error
                    raise TimeoutError('Timeout when receiving data, data config might be wrong.') from None # avoid nested exception
                else:
                    # https://stackoverflow.com/questions/52725278/during-handling-of-the-above-exception-another-exception-occurred
                    raise TimeoutError(f'Timeout when receiving data, pipe is broken: {errmsg}') from None # avoid nested exception
            except Exception as e:
                raise e
        # parse the received data
        frame = self.__parse_recv(recv_data)
        # TODO save frame
        return frame

    def is_server_running(self, serverip, serverport, timeout) -> tuple(bool, str):
        """Test the connection to the server.
        
        Returns:
            bool: Whether the connection is established.
            str: The error message if the connection is not established.
        """
        # test if the server is running
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(timeout)
            return_value = s.connect_ex((serverip, serverport))
            if return_value == 0:
                return True, 'Connection established.'
            elif return_value == 11:
                errmsg = (f'Connection timeout, please check if the port {serverport} on {serverip} is open.')
            elif return_value == 111:
                errmsg = (f'Connection refused, please check if the port {serverport} on {serverip} is in use.')
            elif return_value == 113:
                errmsg = (f'No route to host, please make sure the server {serverip} exists and can be reached.')
            else:
                # see https://github.com/torvalds/linux/blob/master/include/uapi/asm-generic/errno.h for the meaning of error codes
                errmsg = (f'Cannot connect to {serverip}, socket error {return_value}.')
        
        return False, errmsg

    def __get_socket(self, reconnect=False) -> socket.socket:
        """Connect to the server.
        
        Args:
            reconnect (bool, optional): Whether to reconnect to the server. Defaults to False.
                                        If any configuration is changed, set this to True to reconnect.
        """
        if self.client is None or reconnect == True:
            # create a socket object
            try:
                self.client = socket.create_connection((self.serverip, self.serverport), timeout=self.connect_timeout)
            except socket.timeout:
                raise TimeoutError('Timeout when connecting to the server.') from None # avoid nested exception
            except Exception as e:
                raise e
            # set input buffer size
            self.client.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, self.expected_data_length*3)
            # set output buffer size
            self.client.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, self.expected_data_length)

            # test connection
            frame_idx = 1
            config_msg = f"{self.server_dir},{frame_idx},{self.nsamples},{self.nchirps_one_loop},{self.nloops},{self.rx_enable},1000"
            self.client.sendall(config_msg.encode())
            recv_start_flag = self.client.recv(1)
            if recv_start_flag != b'y':
                raise InterruptedError('Cannot start receiving data.')
        return self.client

    def __parse_recv(self, recv_data) -> np.ndarray:
        """Parse the received data as adc frame.
        
        Args:
            recv_data (bytes): The received data.

        Returns:
            np.ndarray: The parsed data.
        """
        # MATLAB equavalent code
        # databody = np.frombuffer(recv_data[self.header_size:], dtype=np.int8)
        # # merge two int8 to int16
        # int16_low = databody[::2]
        # int16_high = databody[1::2]
        # # MATLAB uses 256 * databody_high + databody_low, this performs the same operation
        # adcdata_iq = [(x << 8) + y for x, y in zip(int16_high, int16_low)]
        adcdata = np.frombuffer(recv_data[self.header_size:], dtype=np.int16)
        adcdata = adcdata[::2] + 1j*adcdata[1::2]
        dev1, dev2, dev3, dev4 = np.array_split(adcdata, 4)

        dev1 = dev1.reshape(self.rx_enable, self.nsamples, self.tx_enable*self.nchip, self.nloops, order='F')
        dev2 = dev2.reshape(self.rx_enable, self.nsamples, self.tx_enable*self.nchip, self.nloops, order='F')
        dev3 = dev3.reshape(self.rx_enable, self.nsamples, self.tx_enable*self.nchip, self.nloops, order='F')
        dev4 = dev4.reshape(self.rx_enable, self.nsamples, self.tx_enable*self.nchip, self.nloops, order='F')
        
        dev1 = np.transpose(dev1, (1, 3, 0, 2))
        dev2 = np.transpose(dev2, (1, 3, 0, 2))
        dev3 = np.transpose(dev3, (1, 3, 0, 2))
        dev4 = np.transpose(dev4, (1, 3, 0, 2))

        # reorder Rx antennas
        # TI_Cascade_RX_ID = [13 14 15 16 1 2 3 4 9 10 11 12 5 6 7 8 ]
        # device_id = [4, 1, 3, 2]
        # TODO use config file to get the order of Rx antennas
        assert dev1.dtype == dev2.dtype == dev3.dtype == dev4.dtype, "Data types of all devices are not the same."
        complextype = dev1.dtype
        frame = np.zeros((self.nsamples, self.nloops, self.rx_enable*self.nchip, self.tx_enable*self.nchip), dtype=complextype)
        frame[:, :, 0:4, :] = dev4
        frame[:, :, 4:8, :] = dev1
        frame[:, :, 8:12, :] = dev3
        frame[:, :, 12:16, :] = dev2

        return frame


    def enable_save(save_dir, frame_period):
        pass


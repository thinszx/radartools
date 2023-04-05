"""
This file contains the AWR2243 data reader class 
and is modified from https://github.com/azinke/mmwave-repack/blob/main/repack.py
"""

import glob
import numpy as np
import os.path as osp
from datetime import timedelta, datetime

from config import BaseConfig

class AWR2243Reader():
    """AWR2243 data reader class."""

    def __init__(self, workdir, nloops, nsamples):
        """Initialize the AWR2243 data reader.

        Args:
            workdir (str): Directory of the AWR2243 data files which stores data as 
                            - master_XXXX_data.bin, master_XXXX_idx.bin
                            - slave1_XXXX_data.bin, slave1_XXXX_idx.bin
                            - slave2_XXXX_data.bin, slave2_XXXX_idx.bin
                            - slave3_XXXX_data.bin, slave3_XXXX_idx.bin

        """
        self.workdir = workdir

        # set the parameters of radar cube
        self.ntx = 3 # number of transmit antennas in one chip
        self.nrx = 4
        self.nsamples = nsamples
        self.nwave = 2 # real and imaginary i.e. I and Q
        self.nchip = 4 # number of 4 cascaded chips
        # note that the number of chirps in the radar cube is not equal to the number of chirps in final data
        self.nloops = nloops # number of loops in the radar cube, equals to the number of chirps in final data

        # self.XXX_recordings format:
        # {
        #     "data": [{path of master_0000_data.bin}, {path of master_0001_data.bin}, ...],
        #     "idx":  [{path of master_XXXX_idx.bin},  {path of master_XXXX_idx.bin},  ...]
        # }
        self.master_recordings: dict[str, list[str]] = self._get_recordings('master')
        self.slave1_recordings: dict[str, list[str]] = self._get_recordings('slave1')
        self.slave2_recordings: dict[str, list[str]] = self._get_recordings('slave2')
        self.slave3_recordings: dict[str, list[str]] = self._get_recordings('slave3')

        assert self.master_recordings != None, "Error with master data files"
        assert self.slave1_recordings != None, "Error with slave1 data files"
        assert self.slave2_recordings != None, "Error with slave2 data files"
        assert self.slave3_recordings != None, "Error with slave3 data files"

        # avoid reading the same data file multiple times
        self._current_capture_info = [-1, (None, None, None)] # [capture_idx, (frame_num, datasize, timestamp)]
    
    def change_workdir(self, workdir):
        """Change the work directory of the AWR2243 data reader.

        Args:
            workdir (str): Directory of the AWR2243 data files which stores data as 
                            - master_XXXX_data.bin, master_XXXX_idx.bin
                            - slave1_XXXX_data.bin, slave1_XXXX_idx.bin
                            - slave2_XXXX_data.bin, slave2_XXXX_idx.bin
                            - slave3_XXXX_data.bin, slave3_XXXX_idx.bin
        """
        self.workdir = workdir
        self.master_recordings: dict[str, list[str]] = self._get_recordings('master')
        self.slave1_recordings: dict[str, list[str]] = self._get_recordings('slave1')
        self.slave2_recordings: dict[str, list[str]] = self._get_recordings('slave2')
        self.slave3_recordings: dict[str, list[str]] = self._get_recordings('slave3')
        assert self.master_recordings != None, "Error with master data files"
        assert self.slave1_recordings != None, "Error with slave1 data files"
        assert self.slave2_recordings != None, "Error with slave2 data files"
        assert self.slave3_recordings != None, "Error with slave3 data files"

    @classmethod
    def from_config(self, config: BaseConfig, data_dir: str) -> 'AWR2243Reader':
        """Initialize the AWR2243 data reader from the config file.

        Args:
            config (BaseConfig): Config file object, can be Python or JSON config object.
            data_dir (str): Directory of the AWR2243 data files which stores data as *.bin.

        Returns:
            AWR2243Reader: AWR2243 data reader
        """
        nloops = config.loops_per_frame
        nsamples = config.adc_samples
        reader = AWR2243Reader(data_dir, nloops, nsamples)
        reader.ntx = config.tx # number of transmit antennas in one chip
        reader.nrx = config.rx
        reader.nwave = 2 # real and imaginary i.e. I and Q
        reader.nchip = config.devices # number of 4 cascaded chips
        # note that the number of chirps in the radar cube is not equal to the number of chirps in final data
        reader.master_recordings: dict[str, list[str]] = reader._get_recordings('master')
        reader.slave1_recordings: dict[str, list[str]] = reader._get_recordings('slave1')
        reader.slave2_recordings: dict[str, list[str]] = reader._get_recordings('slave2')
        reader.slave3_recordings: dict[str, list[str]] = reader._get_recordings('slave3')

        assert reader.master_recordings != None, "Error with master data files"
        assert reader.slave1_recordings != None, "Error with slave1 data files"
        assert reader.slave2_recordings != None, "Error with slave2 data files"
        assert reader.slave3_recordings != None, "Error with slave3 data files"

        return reader

    def readframe(self, capture_idx, frame_idx) -> np.ndarray:
        """Read the data and index files of the frame provided in argument.
           This function executes steps logically consistent with the TI code
           'read_ADC_bin_TDA2_separateFiles' and 'readBinFile'.

        Args:
            capture_idx (int): Capture number
            frame_idx (int): Frame index

        Returns:
            tuple: (data, idx)
        """
        # 1. build the path of the data files
        master_datapath = osp.join(self.workdir, f'master_{capture_idx:04d}_data.bin')
        slave1_datapath = osp.join(self.workdir, f'slave1_{capture_idx:04d}_data.bin')
        slave2_datapath = osp.join(self.workdir, f'slave2_{capture_idx:04d}_data.bin')
        slave3_datapath = osp.join(self.workdir, f'slave3_{capture_idx:04d}_data.bin')

        # check if the files exist
        assert osp.exists(master_datapath), f"File {master_datapath} does not exist."
        
        # 2. load data from capture_idx files
        frame_num, _, _ = self.get_capture_info(capture_idx)
        assert frame_idx < frame_num, f"Frame index {frame_idx} of capture {capture_idx} is out of total 0-{frame_num-1} frames range."

        # 3. prepare to load data, note that count is in the unit of 16-bit integers while offset is in bytes
        # number of items to read (here items are 16-bit integer values)
        # IQ * adcsamples * loops * [rx * (tx * chips)]
        # - (tx * chips) is the number of transmitted chirps in one loop
        # - [rx * (tx * chips)] is all reveived chirps in one loop of ONE BOARD
        nitems: int = self.nwave * self.nsamples * self.nloops * self.nrx * self.ntx * self.nchip
        # offet to read the bytes of a given frame
        # the multiplication by "2" is to count for the size of 16-bit integers
        offset: int = frame_idx * nitems * 2

        # 4. load data
        # original MATLAB code uses uint16 and converts uint16 to int16 by:
        #     neg             = logical(bitget(adcData1, 16));
        #     adcData1(neg)   = adcData1(neg) - 2^16;
        # with my test there's no any difference using np.int16 in python to read the data directly compared with:
        #     neg = np.bitwise_and(adcData1, 0b1000000000000000).astype(bool) # equals to 0x8000
        #     adcData1[neg] = adcData1[neg] - 2**16
        #     adcData1 = adcData1.astype(np.int16)
        dev1 = np.fromfile(master_datapath, dtype=np.int16, count=nitems, offset=offset)
        dev2 = np.fromfile(slave1_datapath, dtype=np.int16, count=nitems, offset=offset)
        dev3 = np.fromfile(slave2_datapath, dtype=np.int16, count=nitems, offset=offset)
        dev4 = np.fromfile(slave3_datapath, dtype=np.int16, count=nitems, offset=offset)

        dev1 = dev1[::2] + 1j*dev1[1::2]
        dev2 = dev2[::2] + 1j*dev2[1::2]
        dev3 = dev3[::2] + 1j*dev3[1::2]
        dev4 = dev4[::2] + 1j*dev4[1::2]

        # 5. reshape data into radar cube
        # ntx*nchip(12) means all chirps transmitted in one loop from 12Tx of 4 chips
        # order='F' means Fortran order, which is column-major order the same as in MATLAB
        # see https://en.wikipedia.org/wiki/Row-_and_column-major_order for more details
        dev1 = dev1.reshape(self.nrx, self.nsamples, self.ntx*self.nchip, self.nloops, order='F')
        dev2 = dev2.reshape(self.nrx, self.nsamples, self.ntx*self.nchip, self.nloops, order='F')
        dev3 = dev3.reshape(self.nrx, self.nsamples, self.ntx*self.nchip, self.nloops, order='F')
        dev4 = dev4.reshape(self.nrx, self.nsamples, self.ntx*self.nchip, self.nloops, order='F')

        dev1 = np.transpose(dev1, (1, 3, 0, 2))
        dev2 = np.transpose(dev2, (1, 3, 0, 2))
        dev3 = np.transpose(dev3, (1, 3, 0, 2))
        dev4 = np.transpose(dev4, (1, 3, 0, 2))

        # 6. merge data from all devices according to AWR2243 cascaded chip order
        # the RX channels are re-ordered according to "TI_Cascade_RX_ID" defined in "module_params.m"
        # TODO use config file to define the order of the chips
        # TODO TI_Cascade_RX_ID = [13 14 15 16 1 2 3 4 9 10 11 12 5 6 7 8 ]; %RX channel order on TI 4-chip cascade EVM
        assert dev1.dtype == dev2.dtype == dev3.dtype == dev4.dtype, "Data types of all devices are not the same."
        complextype = dev1.dtype
        frame = np.zeros((self.nsamples, self.nloops, self.nrx*self.nchip, self.ntx*self.nchip), dtype=complextype)
        frame[:, :, 0:4, :] = dev4
        frame[:, :, 4:8, :] = dev1
        frame[:, :, 8:12, :] = dev3
        frame[:, :, 12:16, :] = dev2

        return frame

    def _get_recordings(self, device):
        """Load the recordings of the radar chip provided in argument.

        Args:
            device (str): Name of the device, i.e. "master", "slave1", "slave2", "slave3"

        Return:
            Dictionary containing the data and index files
        """
        # Collection of the recordings data file
        # They all have the "*.bin" ending
        recordings: dict[str, list[str]] = {
            "data": glob.glob(osp.join(self.workdir, f"{device}*data.bin")),
            "idx": glob.glob(osp.join(self.workdir, f"{device}*idx.bin"))
        }
        recordings["data"].sort()
        recordings["idx"].sort()

        if (len(recordings["data"]) == 0) or (recordings["idx"] == 0):
            print(f"[ERROR]: No file found for device '{device}'")
            return None
        elif len(recordings["data"]) != len(recordings["idx"]):
            print(
                f"[ERROR]: Missing {device} data or index file!\n"
                "Please check your recordings!"
                "\nYou must have the same number of "
                "'*data.bin' and '*.idx.bin' files."
            )
            return None
        return recordings

    def get_capture_info(self, capture_idx: int) -> tuple[int, int, np.ndarray]:
        """Get information about the recordings.

        The "*_idx.bin" files along the sample files gather usefule
        information aout the dataset.

        The structure of the "*_idx.bin" file is as follow:

        ---------------------------------------------------------------------------
            File header in *_idx.bin:
                struct Info
                {
                    uint32_t tag;
                    uint32_t version;
                    uint32_t flags;
                    uint32_t numIdx;       // number of frames
                    uint64_t dataFileSize; // total data size written into file
                };

            Index for every frame from each radar:
                struct BuffIdx
                {
                    uint16_t tag;
                    uint16_t version; /*same as Info.version*/
                    uint32_t flags;
                    uint16_t width;
                    uint16_t height;

                    /*
                    * For image data, this is pitch. For raw data, this is
                    * size in bytes per metadata plane
                    */
                    uint32_t pitchOrMetaSize[4];

                    /*
                    * Total size in bytes of the data in the buffer
                    * (sum of all planes)
                    */
                    uint32_t size;
                    uint64_t timestamp; // timestamp in ns
                    uint64_t offset;
                };

        ---------------------------------------------------------------------------

        Args:
            capture_idx (int): Index number of captures

        Return:
            Tuple containing respectively the number of valid frames recorded,
            the size of the data file and timestamps of the frames.
        
        NOTE:
            Modified from example matlab script provided by Texas Instrument
        """
        if capture_idx < 0:
            raise ValueError("Invalid capture index {capture_idx}}")
        # avoid reloading the same file
        if self._current_capture_info[0] == capture_idx:
            return self._current_capture_info[1]
        # Data type based on the structure of the file header
        dt = np.dtype([
            ("tag", np.uint32),
            ("version", np.uint32),
            ("flags", np.uint32),
            ("numIdx", np.uint32),
            ("size", np.uint64),
        ])
        idx_file = osp.join(self.workdir, f"master_{capture_idx:04d}_idx.bin")
        header = np.fromfile(idx_file, dtype=dt, count=1)[0]

        dt = np.dtype([
            ("tag", np.uint16),
            ("version", np.uint16),
            ("flags", np.uint32),
            ("width", np.uint16),
            ("height", np.uint16),

            ("_meta0", np.uint32),
            ("_meta1", np.uint32),
            ("_meta2", np.uint32),
            ("_meta3", np.uint32),

            ("size", np.uint32),
            ("timestamp", np.uint64),
            ("offset", np.uint64),
        ])

        data = np.fromfile(idx_file, dtype=dt, count=-1, offset=24)
        timestamps = np.array([
            (datetime.now() + timedelta(seconds=log[-2] * 1e-9)).timestamp()
            for log in data
        ])

        frame_num = header[3]
        data_size = header[4]
        self._current_capture_info = [capture_idx, (frame_num, data_size, timestamps)]
        return frame_num, data_size, timestamps
    
    def count_captures(self):
        """Get the count of captures recorded"""
        # get the path of all the master index files
        all_master_idxfiles = sorted(glob.glob(osp.join(self.workdir, "master_*_idx.bin")),
                                key=lambda x: int(osp.basename(x).split("_")[1]))

        # check if there is any missing index file
        last_master_idxfile = all_master_idxfiles[-1]
        missing_idx = []
        last_idx = int(osp.basename(last_master_idxfile).split("_")[1])
        for i in range(0, last_idx+1):
            if not osp.exists(osp.join(self.workdir, f"master_{i:04d}_idx.bin")):
                missing_idx.append(i)
        Warning(f"Missing index files between 0-{last_idx}: {missing_idx}")
        return len(all_master_idxfiles), missing_idx
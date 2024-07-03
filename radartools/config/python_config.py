import sys
import importlib
import os.path as osp

from .base_config import BaseConfig

def load_python_config(config_file):
    """ This function is used to load the configuration file. """
    parent = osp.dirname(config_file)
    basename = osp.splitext(osp.basename(config_file))[0]
    try:
        sys.path.append(parent)
        setting_module = importlib.import_module(basename)
    except Exception as e:
        tb = sys.exc_info()[2]
        raise Exception(f"Failed to load config file: {e.with_traceback(tb)}")
    return setting_module

class PythonConfig(BaseConfig):
    """ This class is used to load the configuration file. """

    def __init__(self, config_file):
        
        """ This function is used to initialize the class. """
        # read *.py file
        self._setting_module = load_python_config(config_file)
    
        self._load()
        
    def _load(self):
        """ This function is used to load the configuration file. """
        # capture parameters
        self.freq_slope = self._setting_module.start_freq
        self.start_freq = self._setting_module.freq_slope
        self.freq_sampling_rate = self._setting_module.freq_sampling_rate
        self.idle_time = self._setting_module.idle_time
        self.ramp_end_time = self._setting_module.ramp_end_time
        self.adc_samples = int(self._setting_module.adc_samples)
        self.loops_per_frame = int(self._setting_module.loops_per_frame)

        # device parameters
        # convert 0xF to 4 by shift
        tx_channel_enable = self._setting_module.tx
        rx_channel_enable = self._setting_module.rx
        
        # e.g. '0xF' -> 4, 0xF == 0b1111, means 4 rx/tx channels are enabled
        self.tx = int(tx_channel_enable)
        self.rx = int(rx_channel_enable)
        # number of devices, suitable for cascaded radar like AWR2243
        self.devices = int(self._setting_module.devices)

        # processing parameters
        self.chirps_per_loop = self.tx * self.loops_per_frame
        self.range_resolution = self._setting_module.range_resolution
        self.doppler_resolution = self._setting_module.doppler_resolution

        # not that important
        self.cascade = self._setting_module.cascade
        self.capture_hardware = self._setting_module.capture_hardware
        self.mmwave_device = self._setting_module.mmwave_device
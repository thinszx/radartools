import json
import glob
import numpy as np
import os.path as osp

from .base_config import BaseConfig

class JSONConfig(BaseConfig):
    """ This class is used to load the configuration file. """

    def __init__(self, config_file):
        
        """ This function is used to initialize the class. """
        # read *.mmwave.json file
        try:
            with open(config_file, 'r') as file:
                self.__content = json.load(file)
            self.source = config_file
        except FileNotFoundError:
            print(f"Config file '{config_file}' not found!")
            raise FileNotFoundError
        except json.decoder.JSONDecodeError:
            print(f"JSON file '{config_file}' is not valid!")
            raise json.decoder.JSONDecodeError
    
        self._load()
        
    def _load(self):
        """ This function is used to load the configuration file. """
        profiles = self.__content['mmWaveDevices'][0]['rfConfig']['rlProfiles'][0]['rlProfileCfg_t']

        # capture parameters
        self.freq_slope = profiles['freqSlopeConst_MHz_usec'] * 1e12 # Mhz to Hz and us to s
        self.start_freq = profiles['startFreqConst_GHz']
        self.freq_sampling_rate = profiles['digOutSampleRate'] * 1e3 # ksps to sps
        self.idle_time = profiles['idleTimeConst_usec'] * 1e-6 # us to s
        self.ramp_end_time = profiles['rampEndTime_usec'] * 1e-6 # us to s
        self.adc_samples = int(profiles['numAdcSamples'])
        self.loops_per_frame = int(self.__content['mmWaveDevices'][0]['rfConfig']['rlFrameCfg_t']['numLoops'])

        # device parameters
        # convert 0xF to 4 by shift
        tx_channel_enable = self.__content['mmWaveDevices'][0]['rfConfig']['rlChanCfg_t']['txChannelEn']
        rx_channel_enable = self.__content['mmWaveDevices'][0]['rfConfig']['rlChanCfg_t']['rxChannelEn']
        
        # number of devices, suitable for cascaded radar like AWR2243
        self.devices = len(self.__content['mmWaveDevices'])
        # e.g. '0xF' -> 4, 0xF == 0b1111, means 4 rx/tx channels are enabled
        self.tx = int(np.log2(int(tx_channel_enable, base=16) + 1))
        self.rx = int(np.log2(int(rx_channel_enable, base=16) + 1))

        # processing parameters
        self.chirps_per_loop = self.tx * self.loops_per_frame
        self.range_resolution = (3e8 * self.freq_sampling_rate) / (2 * self.freq_slope * self.adc_samples)
        self.doppler_resolution = 3e8 / (2 * self.start_freq * (self.idle_time + self.ramp_end_time) * self.chirps_per_loop)

        # not that important
        if self.__content['mmWaveDevices'][0]['rfConfig']['rlChanCfg_t']['cascading'] != 0:
            self.cascade = True
        else:
            self.cascade = False
        
        parent_dir = osp.dirname(self.source)
        setupfiles = glob.glob(osp.join(parent_dir, '*.setup.json'))
        assert len(setupfiles) <= 1, f"Only one setup file is allowed in '{parent_dir}'."
        if len(setupfiles) == 1:
            with open(setupfiles[0], 'r') as file:
                setup = json.load(file)
            self.capture_hardware = setup['captureHardware']
            self.mmwave_device = setup['mmWaveDevice']

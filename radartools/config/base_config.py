""" This file contains functions used to load the configuration file. """

class BaseConfig():
    """ This class is used to load the configuration file. """

    def __init__(self):
        """ This function is used to initialize the class. """
        # capture parameters
        self.freq_slope = 0.0
        self.start_freq = 0.0
        self.freq_sampling_rate = 0e6
        self.idle_time = 0e-6
        self.ramp_end_time = 0e-6
        self.adc_samples = 0
        self.loops_per_frame = 0

        # device parameters
        self.tx = 0
        self.rx = 0
        self.devices = 0 # number of devices, suitable for cascaded radar like AWR2243

        # processing parameters
        self.chirps_per_loop = 0
        self.range_resolution = 0.0
        self.doppler_resolution = 0.0

        # not that important
        self.capture_hardware = None
        self.mmwave_device = None
        self.source = None
        self.cascade = False

    def _load(self):
        """ This function is used to load the configuration file. """
        raise NotImplementedError



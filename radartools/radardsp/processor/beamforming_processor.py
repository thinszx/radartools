'''
@File    :  beamforming_processor.py
@Time    :  2023/03/14 16:14:44
@Author  :  Zixin Shang @ thinszx
@Version :  0.1
@Contact :  zxshang@mail.ustc.edu.cn
@Desc    :  This file contains the class for beamforming processing.
@TODO    :  1. Perform beamforming without using configs to make codes more flexible.
            2. Process beamforming directly without crop.
            3. Read settings from test1_param.py.
'''
try:
    import cupy as np
except ImportError:
    import numpy as np
    import warnings
    warnings.filterwarnings('always')
    warnings.warn('Cupy is not installed, using numpy instead.', ImportWarning)
from types import ModuleType

from ...config.python_config import load_python_config



class BeamformingProcessor():
    """ This class is used to perform beamforming processing. """

    def __init__(self, settings):
        """ This function is used to initialize the class. """
        self._all_config = load_python_config(settings)

        # using this class doesn't matter the original config at all
        # this is just for easy reading and coding for you to know what is needed when processing
        self.cfg = ModuleType('_', '_')
        self.cfg.beamforming = self._all_config.beamforming
        self.cfg.constants = self._all_config.constants
        self.cfg.capture = self._all_config.capture
        self.cfg.layout = self._all_config.layout

        # generate virtual array layout
        rxl = self.cfg.layout['rxl']
        txl = self.cfg.layout['txl']
        azi_idx_sum = []
        ele_idx_sum = []
        for _, raz, rel in rxl:
            for _, taz, tel in txl:
                azi_idx_sum.append(taz+raz)
                ele_idx_sum.append(tel+rel)

        self.azi_size = max(azi_idx_sum) + 1 # the "+1" is to count for the 0-indexing used
        self.ele_size = max(ele_idx_sum) + 1

        self.azimuthonly_antnum = self.azi_size
        # select the index with the most azimuth antennas as the elevation index to perform 2D beamforming
        most_azi_idx = azi_idx_sum.index(max(azi_idx_sum))
        self.elevation_antidx = ele_idx_sum[most_azi_idx]

        # construct angle and range grids for beamforming process
        self._x_hor_list = np.linspace(*self.cfg.beamforming['xrange'], num=self.cfg.beamforming['xblocks'])
        self._y_hor_list = np.linspace(*self.cfg.beamforming['yrange'], num=self.cfg.beamforming['yblocks'])

        self._angle_grid = self._generate_angle_grid()
        self._range_grid = self._generate_range_grid()
    
    def _extract_azimuth_only(self, va_adc) -> np.ndarray:
        """ This function is used to extract azimuth only data. 

        Args:
            va_adc (np.ndarray): The input data in virtual array layout with shape 
                                 (nsamples, nloops, elevation_size, azimuth_size).

        Returns:
            azimuthonly_data (np.ndarray): The azimuth only data with shape (nsamples, azimuth_size).
        """
        # TODO this might only be suitable for 2243, make this more flexible on other MIMO system?
        # TODO is the last chirp enough?
        azimuthonly_data = va_adc[:, -1, self.elevation_antidx, :].squeeze()
        azimuthonly_data = np.array(azimuthonly_data, dtype=np.csingle) # convert to cupy array if possible
        return azimuthonly_data

    def process(self, va_adc) -> np.ndarray:
        """ This function is used to perform beamforming processing on virtual array. 
        
        Args:
            va_adc (np.ndarray): The input data in virtual array layout
                                 with shape (nsamples, nloops, elevation_size, azimuth_size).
            crop (bool): Whether to crop the data or not. Default is False.

        Returns:
            aoatof_out (np.ndarray): The output AoA-ToF data with shape (xblocks, yblocks).
                                     If `crop==True`, the shape will be (crop_xblocks, crop_yblocks).
        """
        # check input, this might not be enough for non-cascade radars
        assert (va_adc.shape[-2], va_adc.shape[-1]) == (self.ele_size, self.azi_size), \
            "The beamforming input data shape is not correct, " \
            "you might uses the original ADC data instead of virtual array, " \
            "please process data as data flow: \n" \
            "    ADC data -> calibrated data -> virtual array -> beamforming."
        
        # perform beamforming
        azimuthonly_data = self._extract_azimuth_only(va_adc) # shape (num_samples, azimuth_size)
        aoatof_result = self._angle_grid.T * (self._range_grid.T @ azimuthonly_data)
        aoatof_result = np.sum(aoatof_result, axis=1) # TODO
        aoatof_reshape = aoatof_result.reshape(self.cfg.beamforming['xblocks'], self.cfg.beamforming['yblocks'], order='F')

        # crop
        if self.cfg.beamforming['crop']:
            xs_idx = np.argmin(abs(self._x_hor_list-self.cfg.beamforming['crop_xrange'][0]))
            xe_idx = np.argmin(abs(self._x_hor_list-self.cfg.beamforming['crop_xrange'][1]))
            ys_idx = np.argmin(abs(self._y_hor_list-self.cfg.beamforming['crop_yrange'][0]))
            ye_idx = np.argmin(abs(self._y_hor_list-self.cfg.beamforming['crop_yrange'][1]))

            aoatof_out = aoatof_reshape[xs_idx:xe_idx, ys_idx:ye_idx]
            aoatof_out = np.transpose(aoatof_out, (1, 0)) # make y axis first for plotting
        else:
            aoatof_out = np.transpose(aoatof_reshape, (1, 0)) # make y axis first for plotting

        if hasattr(aoatof_out, 'get'):
            aoatof_out = aoatof_out.get() # get cupy array back to numpy array to save
        return aoatof_out

    def _generate_angle_grid(self) -> np.ndarray:
        """ This function is used to generate angle grid. """
        # TODO add formulation
        antanna_num = self.azimuthonly_antnum
        p_1 = np.expand_dims(
            np.linspace(start=1, stop=antanna_num, num=antanna_num), axis=1) - 1
        
        # distance block in x and y axis on horizontal plane
        xmgs, ymgs = np.meshgrid(self._x_hor_list, self._y_hor_list)
        xmgs = xmgs.T.flatten(order='F')
        ymgs = ymgs.T.flatten(order='F')
        # np.spacing(1) == np.finfo(np.float64).eps
        eps = np.finfo(np.float64).eps
        aoasign = np.sign(eps+xmgs[:]).flatten(order='F') # eps avoid xmgs==0
        
        aoas = 90*(1+aoasign) + (-aoasign) * np.rad2deg(np.arctan((ymgs[:]/(0.001+np.abs(xmgs[:])))))
        
        # calculation
        d = self.cfg.beamforming['half_lambda']
        start_freq = self.cfg.capture['params']['start_freq']
        c = self.cfg.constants['C']
        angle_gridhor = np.exp(-1j*2*np.pi*p_1*start_freq*d*(np.cos(np.deg2rad(aoas))/c))
        angle_gridhor = angle_gridhor.astype('csingle') # downsample the accuracy
        return angle_gridhor

    def _generate_range_grid(self) -> np.ndarray:
        """ This function is used to generate range grid. """
        # TODO add formulation
        period = 1/self.cfg.capture['params']['freq_sampling_rate']
        c = self.cfg.constants['C']
        nsamples = self.cfg.capture['params']['adc_samples']
        slope = self.cfg.capture['params']['freq_slope']

        p_1 = np.expand_dims(np.arange(0, nsamples), axis=1) - 1

        xmgs, ymgs = np.meshgrid(self._x_hor_list, self._y_hor_list)
        xmgs = xmgs.T.flatten(order='F')
        ymgs = ymgs.T.flatten(order='F')
        tofs = np.sqrt(xmgs[:]**2+ymgs[:]**2) * 2
        range_gridhor = np.exp(-1j*2*np.pi*p_1*period*slope*tofs/c)
        range_gridhor = range_gridhor.astype('csingle') # downsample the accuracy
        return range_gridhor


params = dict(
    # capture parameters
    start_freq = 79.0000000119209e9         ,
    freq_slope = 3.8479000091552734e+13     ,
    freq_sampling_rate = 8e6                ,
    idle_time = 5e-6                        , # 5us
    adc_samples = 256                       ,
    ramp_end_time = 40e-6                   , # 40us
    loops_per_frame = 1                     ,
)

device = dict(
    # device parameters
    # this should be tx and rx channels enabled on one cascaded device
    tx = 3          ,
    rx = 4          ,
    devices = 4     ,
)

processing = dict(
    # processing parameters
    chirps_per_loop = params['loops_per_frame'] * device['tx'] * device['devices'],
    range_resolution = (3e8 * params['freq_sampling_rate']) / (2 * params['freq_slope'] * params['adc_samples']),
    doppler_resolution = 3e8 / (2 * params['start_freq'] * (params['idle_time'] + params['ramp_end_time']) \
                                 * params['loops_per_frame'] * device['tx'] * device['devices']), # chirps_per_loop
)

misc = dict(
    # not important, you can leave it as default
    cascade = True,
    capture_hardware = 'TDA2XX',
    mmwave_device = 'awr2243'
)

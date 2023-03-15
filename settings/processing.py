# path: settings/radardsp.py

from config.python_config import load_python_config
from radardsp.utils.preprocess.antennas import load_virtual_array_layout

"""     Load capture parameters     """
_ = './read2243.py'
capture = dict(
    params = load_python_config(_).params,
    device = load_python_config(_).device,
    processing = load_python_config(_).processing,
    misc = load_python_config(_).misc,
)

constants = dict(
    C = 3e8, # speed of light
)

# !!! if you change the index of transmit/receive antennas when capturing, change the index of rx/tx here !!!
# !!! BUT if you don't know what this means, use the default capture lua script and don't change it !!!
"""        Layout parameters        """
# rx/tx positions are re-written by D_TX/D_TX_ele/D_RX/D_RX_ele order in test1_param.m
rx_ele = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
rx_azi = [0, 1, 2, 3, 11, 12, 13, 14, 46, 47, 48, 49, 50, 51, 52, 53]
tx_ele = [0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 4, 6]
tx_azi = [0, 4, 8, 12, 16, 20, 24, 28, 32, 9, 10, 11]

layout = dict(
    # auto generate rxl and txl
    rxl = load_virtual_array_layout(rx_ele, rx_azi, tx_ele, tx_azi)[0],
    txl = load_virtual_array_layout(rx_ele, rx_azi, tx_ele, tx_azi)[1],
)


"""      Beamforming parameters     """
beamforming = dict(
    xrange = [-10, 10],
    yrange = [0.1, 20],
    # TODO use resolution instead
    xblocks = 401,
    yblocks = 399,

    crop = True,
    crop_xrange = [-5, 5],
    crop_yrange = [0.05, 8],

    # auto generate
    half_lambda = 0.5 * constants['C'] / capture['params']['start_freq'], # distance between two antennas
)

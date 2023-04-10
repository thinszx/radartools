# radartools

## Usage

### Config Setup

- To use configs generated by Mmwave Studio, you can set the parameters by `ConfigJSONLoader` class.
- To use configs as you want, you can set the parameters in `configs.py` and load the data by `ConfigPythonLoader` class. Please make sure you really know the meaning of each parameter because the parameter settings will effect the whole process of data reading and processing.

## Installation

Install this repo as package `radartools` with following command:
```bash
pip install "radartools @ git+http://iplab-ustc.site/gitlab/thinszx/radartools.git@main"
```

If you want to use GPU, use following command instead:
```bash
pip install "radartools[gpu] @ git+http://iplab-ustc.site/gitlab/thinszx/radartools.git@main"
```

## Features

- [x] Detailed examples.
- [x] Supply as Python package.
- [x] Support GPU acceleration.
- [ ] Export data as multiple types.

## Examples

- [x] 2D Beamforming
- [x] AWR2243 layout
- [x] Point cloud generation with 4-D FFT (reorganizing codes, not released yet)

## Credits

- <https://github.com/azinke/mmwave-repack>
- TI official SDK

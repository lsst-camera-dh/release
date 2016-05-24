# release
This is a package to manage the installation of LSST Camera Data Handling software.

## Package versioning
These files identify the repository tags for the packages in `lsst-camera-dh` under CCB control which are to be installed.  The different `packageLists/*_versions.txt` files apply in the corresponding context, e.g., `SLAC_Offline_versions.txt` contains the packages (and their versions) that are to be installed at SLAC for the offline analyses run under [eTraveler](http://lsst-camera.slac.stanford.edu/eTraveler/exp/LSST-CAMERA/welcome.jsp).

## Using the installation script
### Prerequisites
- Anaconda Python installation
- LSST Stack installation
- `datacat` module (for [Data Catalog](http://srs.slac.stanford.edu/DataCatalog/?experiment=LSST-CAMERA) queries at SLAC)

### Example installation sequence:
```
$ git clone git@github.com:lsst-camera-dh/release.git
$ release/bin/install --help
usage: install.py [-h] [--inst_dir INST_DIR] [--site SITE]
                  [--hj_folders HJ_FOLDERS] [--ccs_inst_dir CCS_INST_DIR]
                  version_file

Job Harness Installer

positional arguments:
  version_file          software version file

optional arguments:
  -h, --help            show this help message and exit
  --inst_dir INST_DIR   installation directory
  --site SITE           Site (SLAC, BNL, etc.)
  --hj_folders HJ_FOLDERS
  --ccs_inst_dir CCS_INST_DIR
  
$ mkdir <install directory>
$ release/bin/install.py --inst_dir <install directory> release/packageLists/SLAC_Offline_versions.txt
```
`inst_dir` defaults to `.`

`site` defaults to `SLAC [BNL, SLAC]`

`hj_folders` defaults to `BNL_T03` and determines which files in the `harnessed-jobs` repository are copied to the `share` directory.

`ccs_inst_dir` points to the CCS installation directory where it will install the CCS code.  By default, the CCS code will not be installed.

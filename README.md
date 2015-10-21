# release
upper level package to handle releases of LSST camera data software
Include the installation script and versioning history for the lsst-camera-dh packages.

## versions.txt
Identifies repository tags for all packages in lsst-camera-dh under CCB control which must be installed.
There are both dev and prod lists of package tags.

## How to use the install.py script
### Prerequisites
- Anaconda Python installation
- DMstack installation

### Example Execution
python install.py --inst_dir <path to JH installation> --site SLAC --hj_folders SLAC --prod ../versions.t
inst_dir defaults to .  The install directory must already exist.
site defaults to BNL [BNL, SLAC]
hj_folders defaults to BNL_T03 [BNL_T03, SLAC]  determines what files are copied to the share directory under harnessed-jobs
prod is an optional parameter indicating installation of production release tags
ccd_inst_dir is optional and points to the CCS installation directory

eotest_version=0.0.3
harnessedjobs_version=0.1.3
lcatrHarness_version=0.7.0
lcatrSchema_version=0.4.3
lcatrModulefiles_version=0.3.1

inst_dir=$( cd $(dirname $BASH_SOURCE); pwd -P )

#
# Install modules
#
curl -L -O http://sourceforge.net/projects/modules/files/Modules/modules-3.2.10/modules-3.2.10.tar.gz
tar xzf modules-3.2.10.tar.gz
cd modules-3.2.10
./configure --prefix=${inst_dir} --with-tcl-lib=/usr/lib --with-tcl-inc=/usr/include
make
make install
cd ${inst_dir}

#
# Setup the LSST stack to ensure we are using anaconda python
#
stack_dir=/opt/lsst/redhat6-x86_64-64bit-gcc44/DMstack/Winter2015/
source ${stack_dir}/loadLSST.bash

#
# Add a local ups_db path to declare eotest with eups
#
mkdir -p ${inst_dir}/eups/ups_db
export EUPS_PATH=${inst_dir}/eups:${EUPS_PATH}

#
# Install lcatr packages in ${inst_dir}/lib
#
curl -L -O https://github.com/lsst-camera-dh/lcatr-harness/archive/${lcatrHarness_version}.tar.gz
tar xzf ${lcatrHarness_version}.tar.gz
cd lcatr-harness-${lcatrHarness_version}/
python setup.py install --prefix=${inst_dir}
cd ${inst_dir}

curl -L -O https://github.com/lsst-camera-dh/lcatr-schema/archive/${lcatrSchema_version}.tar.gz
tar xzf ${lcatrSchema_version}.tar.gz
cd lcatr-schema-${lcatrSchema_version}/
python setup.py install --prefix=${inst_dir}
cd ${inst_dir}

curl -L -O https://github.com/lsst-camera-dh/lcatr-modulefiles/archive/${lcatrModulefiles_version}.tar.gz
tar xzf ${lcatrModulefiles_version}.tar.gz
cd lcatr-modulefiles-${lcatrModulefiles_version}/
python setup.py install --prefix=${inst_dir}
ln -sf ${inst_dir}/share/modulefiles ${inst_dir}/Modules
cd ${inst_dir}

touch `ls -d ${inst_dir}/lib/python*/site-packages/lcatr`/__init__.py

curl -L -O https://github.com/lsst-camera-dh/eotest/archive/${eotest_version}.tar.gz
tar xzf ${eotest_version}.tar.gz
cd eotest-${eotest_version}/
eups declare eotest ${eotest_version} -r . -c
setup eotest
setup mysqlpython
scons opt=3
#cd tests
#./run_all.py

cd ${inst_dir}
curl -L -O https://github.com/lsst-camera-dh/harnessed-jobs/archive/${harnessedjobs_version}.tar.gz
tar xzf ${harnessedjobs_version}.tar.gz
#git clone https://github.com/lsst-camera-dh/harnessed-jobs.git
#mv harnessed-jobs harnessed-jobs-${harnessedjobs_version}
#cd harnessed-jobs-${harnessedjobs_version}
#git pull
#git checkout ${harnessedjobs_version}
#cd ${inst_dir}
ln -sf ${inst_dir}/harnessed-jobs-${harnessedjobs_version} ${inst_dir}/harnessed-jobs
ln -sf ${inst_dir}/harnessed-jobs/BNL_T03/* ${inst_dir}/share

echo export STACK_DIR=${stack_dir} > setup.sh
echo source \${STACK_DIR}/loadLSST.bash >> setup.sh
echo export EUPS_PATH=${inst_dir}/eups:\${EUPS_PATH} >> setup.sh
echo setup eotest >> setup.sh
echo setup mysqlpython >> setup.sh
echo export INST_DIR=${inst_dir} >> setup.sh
echo export VIRTUAL_ENV=\${INST_DIR} >> setup.sh
echo source \${INST_DIR}/Modules/3.2.10/init/bash >> setup.sh
#echo export DATACATPATH=/afs/slac/u/gl/srs/datacat/dev/0.3/lib >> setup.sh
echo export HARNESSEDJOBSDIR=\${INST_DIR}/harnessed-jobs-${harnessedjobs_version} >> setup.sh
#echo export PYTHONPATH=\${DATACATPATH}:\${HARNESSEDJOBSDIR}/python:\${INST_DIR}/`ls -d lib/python*/site-packages`:\${PYTHONPATH} >> setup.sh
echo export PYTHONPATH=\${HARNESSEDJOBSDIR}/python:\${INST_DIR}/`ls -d lib/python*/site-packages`:\${PYTHONPATH} >> setup.sh
echo export PATH=\${INST_DIR}/bin:\${PATH} >> setup.sh
echo export SITENAME=BNL >> setup.sh
echo export LCATR_SCHEMA_PATH=\${HARNESSEDJOBSDIR}/schemas:\${LCATR_SCHEMA_PATH} >> setup.sh
echo export LCATR_DATACATALOG_FOLDER=/LSST/Dev/mirror/SLAC >> setup.sh
echo PS1=\"[jh]$ \" >> setup.sh

(source ./setup.sh; python harnessed-jobs-${harnessedjobs_version}/tests/setup_test.py)

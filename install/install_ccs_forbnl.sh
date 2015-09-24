#!/bin/bash
set -e
TESTSTAND_VERSION="1.0.5"
ARCHON_VERSION="1.1"
LOCALDB_VERSION="1.3.4"
CONSOLE_VERSION="1.6.4"
BASE_URL="http://dev.lsstcorp.org:8081/nexus/service/local/artifact/maven/redirect?r=ccs-maven2-public&g=org.lsst"
function download {
  wget "${BASE_URL}&a=$1&v=$2&e=zip&c=dist" -O temp.zip
  if [ -d $1-$2 ] ; then
  rm -r $1-$2
  fi
  unzip -uo temp.zip
  rm temp.zip  
  ln -sf $1-$2 $1
}
download org-lsst-ccs-subsystem-archon-main ${ARCHON_VERSION}
download org-lsst-ccs-subsystem-archon-buses ${ARCHON_VERSION}
download org-lsst-ccs-subsystem-archon-gui ${ARCHON_VERSION}
download org-lsst-ccs-subsystem-teststand-main ${TESTSTAND_VERSION}
download org-lsst-ccs-subsystem-teststand-buses ${TESTSTAND_VERSION}
download org-lsst-ccs-subsystem-teststand-gui ${TESTSTAND_VERSION}
download org-lsst-ccs-localdb-main ${LOCALDB_VERSION}
download org-lsst-ccs-subsystem-console ${CONSOLE_VERSION}
mkdir bin
cd bin
ln -sf ../org-lsst-ccs-subsystem-teststand-main/bin/ts_bnlts3setup2.sh ts
ln -sf ../org-lsst-ccs-subsystem-teststand-main/bin/ts_bnlts3.sh ts
ln -sf ../org-lsst-ccs-subsystem-teststand-main/bin/CCSbootstrap.sh tsSim
ln -sf ../org-lsst-ccs-subsystem-archon-main/bin/CCSbootstrap.sh archon
ln -sf ../org-lsst-ccs-subsystem-archon-main/bin/CCSbootstrap.sh archonSim
ln -sf ../org-lsst-ccs-subsystem-teststand-gui/bin/CCSbootstrap.sh CCS-Console
ln -sf ../org-lsst-ccs-subsystem-teststand-main/bin/CCSbootstrap.sh JythonConsole
ln -sf ../org-lsst-ccs-subsystem-teststand-main/bin/CCSbootstrap.sh ShellCommandConsole
ln -sf ../org-lsst-ccs-localdb-main/bin/trendingPersister.sh trendingPersister.sh
ln -sf ../org-lsst-ccs-localdb-main/bin/trendingServer.sh trendingServer
ln -sf ../org-lsst-ccs-subsystem-teststand-gui/bin/tsJas.sh tsGui

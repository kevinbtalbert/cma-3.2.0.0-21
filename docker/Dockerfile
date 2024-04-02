ARG BUILD_OS=centos
ARG BUILD_OS_VERSION=7
ARG BUILD_IMAGE_VERSION=centos7.9.2009
ARG PYTHON_VERSION=3.9.8
ARG AIRGAPPED=false
ARG THIRD_PARTY_CONTENT_LOCATION="/third-party-content"

FROM amazonlinux:${BUILD_IMAGE_VERSION} as base-centos-al2023
RUN yum -y install \
    java-11-amazon-corretto \
    tar \
    && yum clean all \
    && rm -rf /var/cache/yum \
# newer ansible needs system LANG to be set to be able to work
ENV LANG C.UTF-8
RUN echo 'Installed prerequisites on amazonlinux:2023...'

FROM registry.access.redhat.com/ubi8/ubi:${BUILD_IMAGE_VERSION} as base-centos-8
RUN yum -y install https://dl.fedoraproject.org/pub/epel/epel-release-latest-8.noarch.rpm \
    java-11-openjdk \
    curl \
    && yum clean all \
    && rm -rf /var/cache/yum
# newer ansible needs system LANG to be set to be able to work
ENV LANG C.UTF-8
RUN echo 'Installed prerequisites on rhel8.x...'

FROM centos:${BUILD_IMAGE_VERSION} as base-centos-7
RUN yum -y install epel-release \
    java-11-openjdk \
    curl \
    && yum clean all \
    && rm -rf /var/cache/yum
# newer ansible needs system LANG to be set to be able to work
ENV LANG en_US.UTF-8
RUN echo 'Installed prerequisites on centos7...'

FROM base-centos-${BUILD_OS_VERSION} as cma-base-centos
RUN yum -y install \
    gcc \
    gcc-c++ \
    git \
    make \
    openssl \
    which \
    wget \
    zlib-devel \
    bzip2-devel \
    openssl-devel \
    sqlite-devel \
    libffi-devel \
    vim \
    rsync \
    && yum clean all \
    && rm -rf /var/cache/yum
RUN echo 'set number' >> "${HOME}/.vimrc"
RUN echo 'Installed common prerequisites on centos...'

FROM cma-base-${BUILD_OS} as cma-python-installation
ARG PYTHON_VERSION
ARG CMA_ROOT_DIR
ENV CMA_HOME=${CMA_ROOT_DIR}
ENV HOME /root
WORKDIR ${HOME}
RUN curl -s -S -L https://raw.githubusercontent.com/pyenv/pyenv-installer/master/bin/pyenv-installer | bash
RUN echo -e "\nexport PYENV_ROOT=\"\$HOME/.pyenv\"\ncommand -v pyenv >/dev/null || export PATH=\"\$PYENV_ROOT/bin:\$PATH\"\neval \"\$(pyenv init -)\"" >> ${HOME}/.bashrc
ENV PYENV_ROOT ${HOME}/.pyenv
ENV PATH ${PYENV_ROOT}/shims:${PYENV_ROOT}/bin:$PATH
RUN eval "$(pyenv init -)"
RUN pyenv install ${PYTHON_VERSION} && pyenv global ${PYTHON_VERSION}
RUN echo "Installed python-${PYTHON_VERSION} ..."

FROM cma-python-installation as cma-python-dependencies-installation-airgapped-false
WORKDIR ${CMA_HOME}
ARG SRC_AM2CM_ANSIBLE
ONBUILD ADD ${SRC_AM2CM_ANSIBLE} am2cm-ansible
ONBUILD RUN pip3 install wheel==0.41.1
ONBUILD RUN pip3 install -r am2cm-ansible/requirements.txt
RUN echo "Pre-installed required Python packages..."

FROM cma-python-installation as cma-python-dependencies-installation-airgapped-true
WORKDIR ${CMA_HOME}
ARG PYTHON_VERSION
ARG CMA_EXTRAS_GPL_TAR
ARG SRC_AM2CM_ANSIBLE
ONBUILD ADD ${SRC_AM2CM_ANSIBLE} am2cm-ansible
ONBUILD ADD ${CMA_EXTRAS_GPL_TAR} am2cm-ansible/python_dependencies
ARG INNER_PYPY_WEBSERVER_PORT=9003
ENV INNER_PYPY_WEBSERVER_PORT ${INNER_PYPY_WEBSERVER_PORT}
ONBUILD RUN (python3 -m http.server ${INNER_PYPY_WEBSERVER_PORT} --directory "am2cm-ansible/python_dependencies" 2>&1 > /dev/null &) && pip3 install -r "am2cm-ansible/python_requirements/control_node_$(echo $PYTHON_VERSION | grep -o -m1 '[0-9][0-9]*\.[0-9][0-9]*')_requirements.txt" -i "http://localhost:${INNER_PYPY_WEBSERVER_PORT}" --trusted-host localhost
RUN echo "Pre-installed required Python packages..."

FROM cma-python-dependencies-installation-airgapped-${AIRGAPPED} as download-jdbc-drivers
ARG THIRD_PARTY_CONTENT_LOCATION
ENV JDBC_DRIVERS_TARGET ${THIRD_PARTY_CONTENT_LOCATION}/jdbc-drivers
RUN mkdir -p ${JDBC_DRIVERS_TARGET}
WORKDIR ${CMA_HOME}/am2cm-ansible
RUN ansible-playbook -e "@inventories/group_vars/all.yml" -e "jdbc_control_node_directory=${JDBC_DRIVERS_TARGET}" playbooks/install/download_jdbc_drivers.yml

FROM download-jdbc-drivers as download-atlas-migration-tool
ARG THIRD_PARTY_CONTENT_LOCATION
ENV ATLAS_MIGRATION_TOOL_DOWNLOAD_DIR ${THIRD_PARTY_CONTENT_LOCATION}
WORKDIR ${CMA_HOME}/am2cm-ansible
RUN ansible-playbook -e "@inventories/group_vars/all.yml" playbooks/install/download_atlas_migration_tool_for_offline_use.yml

FROM download-atlas-migration-tool as cma-final
ARG AIRGAPPED=false
ENV AIRGAPPED ${AIRGAPPED}
ARG SRC_CMA_SERVER=cma-server
ARG SRC_AM2CM_TOOL=am2cm-tool
ARG SRC_AM2CM_UPGRADE=am2cm-upgrade
ARG SRC_AM2CM_DIFF=am2cm-diff
ARG SRC_AM2CM_SOLR_CLIENT=am2cm-solr-client
ARG SRC_STARTUP_SCRIPT=startup.sh
ARG SRC_CMA_PVC_ANSIBLE=cma-pvc-ansible
ARG SRC_CMA_PC_ANSIBLE=cma-pc-ansible
ARG SRC_CMA_TOOLS=cma-tools
ARG CMA_SERVER_PROFILE=prod
WORKDIR ${CMA_HOME}
ADD ${SRC_CMA_SERVER} cma-server
ADD ${SRC_AM2CM_TOOL} am2cm-tool
ADD ${SRC_AM2CM_UPGRADE} am2cm-upgrade
ADD ${SRC_AM2CM_DIFF} am2cm-diff
ADD ${SRC_AM2CM_SOLR_CLIENT} am2cm-solr-client
ADD ${SRC_CMA_PVC_ANSIBLE} cma-pvc-ansible
ADD ${SRC_CMA_PC_ANSIBLE} cma-pc-ansible
ADD ${SRC_CMA_TOOLS} cma-tools
ENV CMA_SERVER_PROFILE ${CMA_SERVER_PROFILE}

# for legacy compatibility:
ENV AM2CM_ROOT ${CMA_HOME}

RUN ln -s ${CMA_HOME}/cma-server/cma-server.sh /usr/local/bin/cma-server.sh
RUN ln -s ${CMA_HOME}/am2cm-tool/am2cm.sh /usr/local/bin/am2cm.sh
RUN ln -s ${CMA_HOME}/am2cm-upgrade/hdp-config-upgrade.sh /usr/local/bin/hdp-config-upgrade.sh
RUN ln -s ${CMA_HOME}/am2cm-diff/am2cm-diff.sh /usr/local/bin/am2cm-diff.sh
RUN ln -s ${CMA_HOME}/am2cm-solr-client/am2cm-solr-client.sh /usr/local/bin/am2cm-solr-client.sh
RUN echo "Setup completed!"
ADD ${SRC_STARTUP_SCRIPT} /usr/local/bin/startup.sh
CMD ["sh", "-c", "startup.sh", "--profile=${CMA_SERVER_PROFILE}", "--pypi-webserver-port=${INNER_PYPY_WEBSERVER_PORT}", "--airgapped=${AIRGAPPED}"]

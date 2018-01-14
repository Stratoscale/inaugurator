define(`KERNEL_VERSION', esyscmd(`printf \`\`%s\'\' "$KERNEL_VERSION"'))

FROM centos:7.3.1611
MAINTAINER korabel@stratoscale.com

# Install other tools
RUN yum update -y && \
    yum -y clean all

RUN yum install -y \
    sudo \
    boost-devel \
    boost-static \
    openssl-devel \
    gcc-c++ \
    hwdata \
    kexec-tools \
    net-tools \
    parted \
    e2fsprogs \
    dosfstools \
    lvm2 \
    make \
    http://yum-repo.dc1/repos/centos/Packages/kernel-3.10.0-514.el7.x86_64.rpm \
    rsync \
    smartmontools && \
    yum -y clean all

# Install PIP (obtained from EPEL)
RUN yum install -y epel-release && \
    yum install -y python-pip && \
    yum -y clean all

# Add the Elrepo repository and install the CCISS driver
RUN rpm --import https://www.elrepo.org/RPM-GPG-KEY-elrepo.org && \
    rpm -Uvh http://www.elrepo.org/elrepo-release-7.0-2.el7.elrepo.noarch.rpm && \
    yum install -y kmod-cciss && \
    yum -y clean all

RUN pip install pep8 pika>=0.10.0

# Edit sudoers file to avoid error: sudo: sorry, you must have a tty to run sudo
RUN sed -i -e "s/Defaults    requiretty.*/ #Defaults    requiretty/g" /etc/sudoers

# Install busybox with a Fedora RPM since there's no such package for Centos 7
RUN curl ftp://195.220.108.108/linux/fedora/linux/releases/25/Everything/x86_64/os/Packages/b/busybox-1.22.1-5.fc24.x86_64.rpm -o temp && \
    rpm -ivh temp && \
    rm temp

WORKDIR /root/inaugurator

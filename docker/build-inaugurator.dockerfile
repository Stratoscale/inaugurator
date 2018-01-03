define(`KERNEL_VERSION', esyscmd(`printf \`\`%s\'\' "$KERNEL_VERSION"'))

FROM centos:7.3.1611
MAINTAINER korabel@stratoscale.com

# Install other tools
RUN yum update -y; exit 0
RUN yum -y clean all

RUN yum install -y sudo; exit 0
RUN yum install -y boost-devel; exit 0
RUN yum install -y boost-static; exit 0
RUN yum install -y openssl-devel; exit 0
RUN yum install -y gcc-c++; exit 0
RUN yum install -y hwdata; exit 0
RUN yum install -y kexec-tools; exit 0
RUN yum install -y net-tools; exit 0
RUN yum install -y parted; exit 0
RUN yum install -y e2fsprogs; exit 0
RUN yum install -y dosfstools; exit 0
RUN yum install -y lvm2; exit 0
RUN yum install -y make; exit 0
RUN yum install -y kernel-KERNEL_VERSION; exit 0
RUN yum install -y rsync; exit 0
RUN yum install -y smartmontools; exit 0
RUN yum install -y make; exit 0
RUN yum -y clean all

# Install PIP (obtained from EPEL)
RUN yum install -y epel-release; exit 0
RUN yum install -y python-pip; exit 0
RUN yum -y clean all

# Add the Elrepo repository and install the CCISS driver
RUN rpm --import https://www.elrepo.org/RPM-GPG-KEY-elrepo.org && \
    rpm -Uvh http://www.elrepo.org/elrepo-release-7.0-2.el7.elrepo.noarch.rpm
RUN yum install -y kmod-cciss; exit 0
RUN yum -y clean all

RUN pip install pep8 pika>=0.10.0

# Edit sudoers file to avoid error: sudo: sorry, you must have a tty to run sudo
RUN sed -i -e "s/Defaults    requiretty.*/ #Defaults    requiretty/g" /etc/sudoers

# Install busybox with a Fedora RPM since there's no such package for Centos 7
RUN curl ftp://ftp.pbone.net/mirror/archive.fedoraproject.org/fedora/linux/releases/23/Everything/x86_64/os/Packages/b/busybox-1.22.1-4.fc23.x86_64.rpm -o temp && \
    rpm -ivh temp && \
    rm temp

WORKDIR /root/inaugurator

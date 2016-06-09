FROM centos:7.2.1511
MAINTAINER eliran@stratoscale.com

# Add the EPEL repository and update all packages
RUN curl http://dl.fedoraproject.org/pub/epel/7/x86_64/e/epel-release-7-5.noarch.rpm -o temp && \
    rpm -ivh temp && \
    rm temp

# Install other tools
RUN yum update -y

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
    python-pip \
    make \
    kernel \
    rsync && \
    tftp && \
    yum -y clean all

RUN pip install pep8 pika>=0.10.0

# Edit sudoers file to avoid error: sudo: sorry, you must have a tty to run sudo
RUN sed -i -e "s/Defaults    requiretty.*/ #Defaults    requiretty/g" /etc/sudoers

# Install busybox with a Fedora RPM since there's no such package for Centos 7
RUN curl ftp://195.220.108.108/linux/fedora/linux/releases/23/Everything/x86_64/os/Packages/b/busybox-1.22.1-4.fc23.x86_64.rpm -o temp && \
    rpm -ivh temp && \
    rm temp

WORKDIR /root

CMD make -C osmosis build -j 10 && \
    make -C osmosis egg

WORKDIR /root/inaugurator
ENV BUILD_HOST local
ENTRYPOINT ["make"]
CMD ["nothing"]

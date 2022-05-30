FROM fedora:28
MAINTAINER ops@lightbitslabs.com

# Install other tools
RUN echo "fastmirror=True" >> /etc/dnf/dnf.conf

RUN dnf update -y

RUN dnf install -y \
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
    lshw \
    pciutils \
    rsync \
    fio \
    ndctl \
    numactl \
    grubby \
    busybox && \
    dnf -y clean all

RUN pip install urllib3 requests pep8 pika==0.13.0

# Edit sudoers file to avoid error: sudo: sorry, you must have a tty to run sudo
RUN sed -i -e "s/Defaults    requiretty.*/ #Defaults    requiretty/g" /etc/sudoers

WORKDIR /root

CMD make -C osmosis build -j 10 && \
    make -C osmosis egg

RUN rpm -i https://rpmfind.net/linux/fedora/linux/releases/32/Everything/x86_64/os/Packages/n/nvme-cli-1.10.1-1.fc32.x86_64.rpm

WORKDIR /root/inaugurator
ENV BUILD_HOST local
ENTRYPOINT ["make"]
CMD ["nothing"]

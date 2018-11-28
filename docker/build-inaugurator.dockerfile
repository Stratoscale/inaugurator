FROM fedora:27
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
    nvme-cli \
    busybox && \
    dnf -y clean all

RUN pip install pep8 pika>=0.10.0

# Edit sudoers file to avoid error: sudo: sorry, you must have a tty to run sudo
RUN sed -i -e "s/Defaults    requiretty.*/ #Defaults    requiretty/g" /etc/sudoers

WORKDIR /root

CMD make -C osmosis build -j 10 && \
    make -C osmosis egg

WORKDIR /root/inaugurator
ENV BUILD_HOST local
ENTRYPOINT ["make"]
CMD ["nothing"]

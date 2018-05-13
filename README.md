The Inaugurator depends on the latest Fedora kernel. You may need to scratch the current inaugurator image if it's not building correctly.


To build:
    dockerize make -d Makefile.lb

If this gets stuck on missing kernels, use `docker rmi fedora:27` and try again.

While it's running, note the version of the kernel RPM getting installed, and in a second terminal update that string into the first line of Makefile.build.

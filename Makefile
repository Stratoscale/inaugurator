all: build check_convention

clean:
	rm -fr build dist inaugurator.egg-info

check_convention:
	pep8 inaugurator --max-line-length=109

include Makefile.build

install: build/inaugurator.initrd.img build/inaugurator.vmlinuz
	-sudo mkdir /usr/share/inaugurator
	sudo cp $^ /usr/share/inaugurator
	sudo chmod 644 /usr/share/inaugurator/*

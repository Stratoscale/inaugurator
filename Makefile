all: build unittest check_convention

clean:
	rm -fr build dist inaugurator.egg-info

check_convention:
	pep8 inaugurator --max-line-length=109 --exclude=samplegrubconfigs.py
	sh/check_spelling.sh

unittest:
	PYTHONPATH=$(PWD) python -m unittest inaugurator.tests.test_grubconfparser

include Makefile.build

install: build/inaugurator.initrd.img build/inaugurator.vmlinuz
	-sudo mkdir /usr/share/inaugurator
	-yes | sudo pip uninstall inaugurator
	sudo python setup.py install
	sudo cp $^ /usr/share/inaugurator
	sudo chmod 644 /usr/share/inaugurator/*

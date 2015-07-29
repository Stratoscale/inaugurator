all: build unittest check_convention

clean:
	rm -fr build dist inaugurator.egg-info

check_convention:
	pep8 inaugurator --max-line-length=109 --exclude=samplegrubconfigs.py,newpika_select_connection.py
	sh/check_spelling.sh

UNITTESTS=$(shell find inaugurator -name 'test*.py' | sed 's@/@.@g' | sed 's/\(.*\)\.py/\1/' | sort)
unittest:
	PYTHONPATH=$(PWD) python -m unittest $(UNITTESTS)

integration_test:
	PIKA_EGG_PATH=pika-stable/pika-0.10.0p0-py2.7-commitref-7f222c29abe.egg PYTHONPATH=inaugurator python inaugurator/tests/test_server.py $(TESTS)

include Makefile.build

uninstall:
	-sudo mkdir /usr/share/inaugurator
	-yes | sudo pip uninstall inaugurator

PRODUCTS = build/inaugurator.thin.initrd.img build/inaugurator.fat.initrd.img build/inaugurator.vmlinuz
install: $(PRODUCTS)
	$(MAKE) install_nodeps

install_nodeps:
	-sudo mkdir /usr/share/inaugurator
	-yes | sudo pip uninstall inaugurator
	sudo python setup.py install
	sudo cp $(PRODUCTS) /usr/share/inaugurator
	sudo cp $(PIKA_EGG_FILENAME) /usr/share/inaugurator
	sudo chmod 644 /usr/share/inaugurator/*

prepareForCleanBuild:
	sudo pip install pika

all: build unittest check_convention

install: images
	$(MAKE) install_nodeps

clean:
	rm -fr build dist inaugurator.egg-info

check_convention:
	pep8 inaugurator --max-line-length=109 --exclude=samplegrubconfigs.py
	sh/check_spelling.sh

UNITTESTS=$(shell find inaugurator -name 'test*.py' | sed 's@/@.@g' | sed 's/\(.*\)\.py/\1/' | sort)
unittest:
	PYTHONPATH=. python -m unittest $(UNITTESTS)

integration_test:
	@echo "Note: For specific tests, run with TESTS=(Space seperated test names)."
	@PYTHONPATH=inaugurator python inaugurator/tests/integration_test.py $(TESTS)

include Makefile.build

uninstall:
	-sudo mkdir /usr/share/inaugurator
	-yes | sudo pip uninstall inaugurator

IMAGES = build/$(IMAGES_SOURCE)/inaugurator.thin.initrd.img build/$(IMAGES_SOURCE)/inaugurator.fat.initrd.img build/$(IMAGES_SOURCE)/inaugurator.vmlinuz

.PHONY: images
images:
ifeq ($(IMAGES_SOURCE),)
	$(error Please specify the environment variable IMAGES_SOURCE, to indicate how to obtain inaugurator images, as either 'build' (build images locally) or 'remote' (bring images from solvent object store))
endif
	$(MAKE) $(IMAGES)

.PHONY: bring_images_from_objectstore
bring_images_from_objectstore:
	-mkdir -p build/remote
	sudo solvent bring --repositoryBasename=inaugurator --product images --destination=build/remote

.PHONY: submitimages
submitimages:
	@stat $(IMAGES) || (echo "Please use the 'build' makefile recipe to build the images first." && exit 1)
	-mkdir build/images_product
	cp $(IMAGES) build/images_product
	solvent submitproduct images build/images_product

build/remote/inaugurator.thin.initrd.img: bring_images_from_objectstore
build/remote/inaugurator.fat.initrd.img: bring_images_from_objectstore
build/remote/inaugurator.vmlinuz: bring_images_from_objectstore

install_nodeps:
	-sudo mkdir /usr/share/inaugurator
	-yes | sudo pip uninstall inaugurator
	python setup.py bdist
	sudo python setup.py install
	sudo cp $(IMAGES) /usr/share/inaugurator
	sudo chmod 644 /usr/share/inaugurator/*

prepareForCleanBuild:
	sudo pip install pika

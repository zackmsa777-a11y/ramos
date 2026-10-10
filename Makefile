AS = as
LD = ld
PYTHON ?= python3
PREFIX ?= /usr/local
DESTDIR ?=
INSTALL ?= install

.PHONY: all test demo calculator control-flow functions buffers install clean
all: ramos

build/ramos.o: src/ramos.s $(wildcard src/*.inc)
	mkdir -p build
	$(AS) --64 -o $@ $<

ramos: build/ramos.o
	$(LD) -z noexecstack --build-id=none -o $@ $<

test: ramos
	$(PYTHON) -m unittest discover -s tests

demo: ramos
	./ramos build example.ramos -o example --force
	./example

calculator: ramos
	./ramos build examples/calculator.ramos -o calculator --force
	./calculator

control-flow: ramos
	./ramos build examples/control_flow.ramos -o build/control-flow --force
	./build/control-flow

functions: ramos
	./ramos build examples/functions.ramos -o build/functions --force
	./build/functions

buffers: ramos
	./ramos build examples/buffers.ramos -o build/buffers --force
	./build/buffers

install: ramos
	$(INSTALL) -d "$(DESTDIR)$(PREFIX)/bin"
	$(INSTALL) -m 755 ramos "$(DESTDIR)$(PREFIX)/bin/ramos"

clean:
	rm -f ramos example calculator build/ramos.o build/control-flow build/functions build/buffers

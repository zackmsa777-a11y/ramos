AS = as
LD = ld
PYTHON ?= python3
PREFIX ?= /usr/local
DESTDIR ?=
INSTALL ?= install

.PHONY: all test demo calculator control-flow install clean
all: ramos

build/ramos.o: src/ramos.s $(wildcard src/*.inc)
	mkdir -p build
	$(AS) --64 -o $@ $<

ramos: build/ramos.o
	$(LD) -z noexecstack --build-id=none -o $@ $<

test: ramos
	$(PYTHON) tests/test_ramos.py

demo: ramos
	./ramos build example.ramos -o example --force
	./example

calculator: ramos
	./ramos build examples/calculator.ramos -o calculator --force
	./calculator

control-flow: ramos
	./ramos build examples/control_flow.ramos -o build/control-flow --force
	./build/control-flow

install: ramos
	$(INSTALL) -d "$(DESTDIR)$(PREFIX)/bin"
	$(INSTALL) -m 755 ramos "$(DESTDIR)$(PREFIX)/bin/ramos"

clean:
	rm -f ramos example calculator build/ramos.o build/control-flow

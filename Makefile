AS = as
LD = ld
PYTHON ?= python3
PREFIX ?= /usr/local
DESTDIR ?=
INSTALL ?= install

.PHONY: all bootstrap selfhost test test-bootstrap demo calculator control-flow functions buffers install clean
all: ramos

build/stage0.o: bootstrap/src/ramos.s $(wildcard bootstrap/src/*.inc)
	mkdir -p build
	$(AS) --64 -o $@ $<
build/stage0: build/stage0.o
	$(LD) -z noexecstack --build-id=none -o $@ $<
bootstrap: build/stage0
build/stage1: build/stage0 compiler/ramos.ramos
	./build/stage0 build compiler/ramos.ramos -o $@ --force
build/stage2: build/stage1 compiler/ramos.ramos
	./build/stage1 build compiler/ramos.ramos -o $@ --force
build/stage3: build/stage2 compiler/ramos.ramos
	./build/stage2 build compiler/ramos.ramos -o $@ --force
ramos: build/stage2
	$(INSTALL) -m 755 $< $@
selfhost: build/stage3
	cmp build/stage2 build/stage3
	$(PYTHON) tools/bootstrap_proof.py
test: ramos
	RAMOS_COMPILER="$(CURDIR)/ramos" $(PYTHON) -m unittest discover -s tests
test-bootstrap: build/stage0
	RAMOS_COMPILER="$(CURDIR)/build/stage0" $(PYTHON) -m unittest discover -s tests

demo: ramos
	./ramos build examples/hello.ramos -o build/hello --force
	./build/hello
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
	rm -rf build ramos example calculator

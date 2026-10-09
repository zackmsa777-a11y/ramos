AS = as
LD = ld
PYTHON ?= python3

.PHONY: all test demo calculator clean
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

clean:
	rm -f ramos example calculator build/ramos.o

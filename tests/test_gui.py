"""GUI validation, static Linux behavior and real Windows desktop apps."""
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import unittest
import test_ramos as support
from test_libraries import BOOTSTRAP
import test_cli_streams as streams


@unittest.skipIf(BOOTSTRAP, 'the retained seed has no GUI intrinsics or weave')
class GUITests(unittest.TestCase):
    setUp = support.RamosTests.setUp
    build = support.RamosTests.build
    build_ok = streams.StreamTests.build_ok
    standard_library = streams.StreamTests.standard_library
    run_native = streams.StreamTests.run_native

    def test_raw_gui_validation_without_window(self):
        self.build_ok('''fn main() {
print(_gui_open("title", -1, 240))
print(_gui_open("title", 320, 0))
print(_gui_control("bad", "text"))
print(buffer_len(_gui_text(99)))
print(io_error())
print(buffer_len(_gui_poll(-2)))
print(io_error())
print(_gui_close())
print(_gui_close())
}''')
        result = self.run_native()
        self.assertEqual(result.returncode, 0, result.stderr)
        expected = b'-22\n-22\n-22\n0\n-9\n0\n-22\n0\n0\n' if os.name == 'nt' or os.environ.get('RAMOS_WINDOWS_COMPILER') else b'-38\n-38\n-38\n0\n-38\n0\n-38\n0\n0\n'
        self.assertEqual(result.stdout, expected)

    def test_gui_property_encoding_and_color_limits(self):
        self.standard_library()
        self.build_ok('''weave "stdlib/gui.ramos"
fn main() {
let p = gui_properties(2,64,12,24,100,32,gui_rgb(55,120,220))
print(buffer_len(p))
print(gui_number(p,0))
print(gui_number(p,8))
print(gui_number(p,16))
print(gui_number(p,48))
}''')
        self.assertEqual(self.run_native().stdout, b'56\n2\n64\n12\n14448695\n')
        for call in ['gui_rgb(-1,0,0)', 'gui_rgb(0,256,0)', 'gui_rgb(0,0,256)', 'gui_properties(1,1,-1,0,10,10,0)']:
            self.build_ok('weave "stdlib/gui.ramos"\nfn main() { '+call+' }')
            result = self.run_native()
            self.assertEqual(result.returncode, 1)
            self.assertIn(b'GUI error', result.stderr)

    def test_gui_intrinsic_types_are_checked(self):
        for call in ['_gui_open(s"x",320,240)', '_gui_open("x",true,240)', '_gui_control("x",1)', '_gui_text("x")', '_gui_poll(true)', '_gui_close(1)']:
            result = self.build('fn main() { '+call+' }', '--force')
            self.assertNotEqual(result.returncode, 0, call)
            self.assertIn(b'error:', result.stderr)

    def test_gui_pe_subsystem_flag_and_invalid_options(self):
        result = self.build('fn main() {}', '--target', 'windows', '--gui')
        self.assertEqual(result.returncode, 0, result.stderr)
        binary = self.output.read_bytes(); nt = struct.unpack_from('<I', binary,60)[0]
        self.assertEqual(struct.unpack_from('<H',binary,nt+24+68)[0],2)
        self.assertNotIn(b'msvcrt.dll',binary.lower())
        self.output.write_bytes(b'preserve')
        for args in [('--target','linux','--gui','--force'), ('--target','windows','--gui','--gui')]:
            result = self.build('fn main() {}', *args)
            self.assertNotEqual(result.returncode,0)
            self.assertEqual(self.output.read_bytes(),b'preserve')


@unittest.skipIf(BOOTSTRAP or not (os.name == 'nt' or os.environ.get('RAMOS_GUI_WINE_PYTHON')), 'requires Windows desktop or explicit Wine desktop harness')
class WindowsGUITests(unittest.TestCase):
    setUp = support.RamosTests.setUp
    build = support.RamosTests.build
    native_path = staticmethod(str)

    def gui_probe(self, mode):
        shutil.copytree(support.ROOT/'stdlib',self.directory/'stdlib',dirs_exist_ok=True)
        if mode == 'notes':
            code=(support.ROOT/'examples/notes.ramos').read_text().replace('../stdlib/','stdlib/')
        else:
            ending='exit(7)' if mode=='exit' else 'print(9223372036854775807 + 1)' if mode=='trap' else ''
            code='''weave "stdlib/gui.ramos"
fn main() {
var i = 0
while i < 12 {
gui_check(gui_open(s"Ramos lifecycle",320,240))
gui_panel(64,0,0,20,20,gui_rgb(55,120,220))
gui_check(gui_close())
i = i + 1 }
gui_check(gui_open(s"Ramos GUI test",320,240))
print(gui_open(s"second",320,240))
gui_label(1,20,20,280,24,s"Ready")
gui_button(2,20,120,100,32,s"Click")
gui_input(3,20,60,280,28,s"initial")
gui_panel(4,0,0,320,6,gui_rgb(55,120,220))
print(_gui_control(gui_properties(1,1,0,0,10,10,0),"duplicate"))
print(_gui_control(gui_properties(1,65,0,0,10,10,0),"bad id"))
print(_gui_control(gui_properties(7,3,0,0,0,10,0),""))
print(_gui_control(gui_properties(6,1,0,0,0,0,0),"a\\0b"))
let invalid = buffer(1)
buffer_set(invalid,0,255)
print(_gui_control(gui_properties(6,1,0,0,0,0,0),invalid))
print(gui_text(3))
i = 0
while i < 40 { let garbage = buffer(1048576)
buffer_set(garbage,0,i)
i = i + 1 }
collect()
gui_set(1,s"Ready after GC")
var running = true
while running {
let e = gui_event(100)
if e.kind == 1 { running = false }
if e.kind == 3 { gui_move(3,20,60,e.width - 40,28) }
if e.kind == 2 && e.id == 2 { print(gui_text(3))
gui_set(1,s"Clicked") }
}
'''+ending+'''
gui_check(gui_close())
print(buffer_len(_gui_text(3)))
print(io_error())
print(gui_close())
}'''
        result=self.build(code,'--force','--gui')
        self.assertEqual(result.returncode,0,result.stderr)
        report=self.directory/'gui.json'
        worker=[sys.executable] if os.name=='nt' else [os.environ.get('RAMOS_WINE','wine'),self.native_path(Path(os.environ['RAMOS_GUI_WINE_PYTHON']))]
        result=subprocess.run([*worker,self.native_path(support.ROOT/'tools/gui_probe.py'),self.native_path(self.output),mode,self.native_path(self.directory),self.native_path(report)],capture_output=True,timeout=90)
        self.assertEqual(result.returncode,0,(result.stdout,result.stderr))
        evidence=json.loads(report.read_text(encoding='utf-8'))
        self.assertTrue(evidence['visible'] and evidence['closed'],evidence)
        if mode!='notes':
            self.assertTrue(evidence['stdout'].startswith('-16\n-17\n-9\n-22\n-22\n-22\ninitial\n'),evidence)
        return evidence

    def test_native_gui_controls_unicode_resize_gc_and_cleanup(self):
        for mode in ('return','exit','trap'):
            with self.subTest(mode=mode): self.gui_probe(mode)

    def test_native_notes_app_save_preservation_and_clear(self):
        self.gui_probe('notes')

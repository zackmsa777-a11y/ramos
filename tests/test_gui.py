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
        result = self.build('fn main() {}', '--target', 'linux', '--gui', '--force')
        self.assertEqual(result.returncode, 0, result.stderr)
        binary = self.output.read_bytes()
        self.assertEqual(binary[:4], b'\x7fELF')
        self.assertEqual(struct.unpack_from('<H',binary,56)[0],7)
        self.assertIn(b'libgtk-3.so.0\0',binary)
        self.output.write_bytes(b'preserve')
        for args in [('--target','linux','--gui','--gui'), ('--target','windows','--gui','--gui')]:
            result = self.build('fn main() {}', *args)
            self.assertNotEqual(result.returncode,0)
            self.assertEqual(self.output.read_bytes(),b'preserve')


    def test_layout_geometry_and_exact_fill(self):
        self.standard_library()
        self.build_ok('''weave "stdlib/gui.ramos"
fn main() {
let area = gui_inset(360,180,20)
print(area.x)
print(area.y)
print(area.width)
print(area.height)
let bounds = gui_rect(10,20,101,60)
let first = gui_row(bounds,0,3,4)
let last = gui_row(bounds,2,3,4)
print(first.x)
print(first.width)
print(last.x)
print(last.width)
let bottom = gui_column(bounds,1,2,6)
print(bottom.y)
print(bottom.height)
for count in 1..65 {
let box = gui_rect(0,0,8192,100)
var edge = 0
for i in 0..count {
let cell = gui_row(box,i,count,3)
if cell.width < 1 || cell.x != edge { exit(1) }
edge = cell.x + cell.width
if i + 1 < count { edge += 3 }
}
if edge != 8192 { exit(1) }
}
print("filled")
}''')
        result=self.run_native()
        self.assertEqual((result.returncode,result.stdout),(0,b'20\n20\n320\n140\n10\n31\n80\n31\n53\n27\nfilled\n'),result.stderr)

    def test_layout_rejects_bad_bounds_spacing_and_mutated_rectangles(self):
        self.standard_library()
        for call in ['gui_rect(-1,0,1,1)','gui_rect(8192,0,1,1)','gui_rect(0,0,0,1)',
                     'gui_inset(10,10,5)','gui_inset(9223372036854775807,10,1)',
                     'gui_row(GuiRect(0,0,10,10),0,0,0)','gui_row(GuiRect(0,0,10,10),2,2,0)',
                     'gui_column(GuiRect(0,0,10,10),0,2,10)',
                     'gui_row(GuiRect(0,0,10,10),0,65,0)',
                     'gui_row(GuiRect(0,0,9223372036854775807,10),0,1,0)']:
            self.build_ok('weave "stdlib/gui.ramos"\nfn main() { '+call+' }')
            result=self.run_native()
            self.assertEqual(result.returncode,1,call)
            self.assertIn(b'invalid layout',result.stderr)

    def test_file_picker_raw_types_and_inactive_status(self):
        for call in ['_gui_choose(s"x","",0)','_gui_choose("x",s"",0)',
                     '_gui_choose("x","",false)','_gui_choose("x","",0,0)']:
            self.assertNotEqual(self.build('fn main() { '+call+' }','--force').returncode,0)
        self.build_ok('fn main() { print(buffer_len(_gui_choose("x","",0)))\nprint(io_error()) }')
        result=self.run_native()
        expected=b'0\n-9\n' if os.name=='nt' or os.environ.get('RAMOS_WINDOWS_COMPILER') else b'0\n-38\n'
        self.assertEqual((result.returncode,result.stdout),(0,expected),result.stderr)


@unittest.skipIf(BOOTSTRAP or not (os.name == 'nt' or os.environ.get('RAMOS_GUI_WINE_PYTHON')), 'requires Windows desktop or explicit Wine desktop harness')
class WindowsGUITests(unittest.TestCase):
    setUp = support.RamosTests.setUp
    build = support.RamosTests.build
    native_path = staticmethod(str)

    def gui_probe(self, mode):
        shutil.copytree(support.ROOT/'stdlib',self.directory/'stdlib',dirs_exist_ok=True)
        if mode in ('notes','dialogs'):
            code=(support.ROOT/'examples/notes.ramos').read_text(encoding='utf-8').replace('../stdlib/','stdlib/')
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
let e = gui_event(-1)
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
        if mode not in ('notes','dialogs'):
            self.assertTrue(evidence['stdout'].startswith('-16\n-17\n-9\n-22\n-22\n-22\ninitial\n'),evidence)
        return evidence

    def test_native_gui_controls_unicode_resize_gc_and_cleanup(self):
        for mode in ('return','exit','trap'):
            with self.subTest(mode=mode): self.gui_probe(mode)

    def test_native_notes_app_save_preservation_and_clear(self):
        self.gui_probe('notes')

    def test_native_notes_file_dialogs_unicode_cancel_and_preservation(self):
        self.gui_probe('dialogs')

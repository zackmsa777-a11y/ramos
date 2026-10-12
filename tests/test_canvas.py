"""Drawing packets and actual native repaint/ownership/clip/resource acceptance."""
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
import test_ramos as support
from test_libraries import BOOTSTRAP
import test_cli_streams as streams
import test_linux_gui as linux_gui
from linux_gui_probe import wait

EXPECTED = '-17\n-9\n-9\n-22\n0\n-9\n' + '-22\n' * 12 + 'closed\n'

@unittest.skipIf(BOOTSTRAP, 'seed has no drawing library')
class CanvasTests(unittest.TestCase):
    setUp = support.RamosTests.setUp
    build = support.RamosTests.build
    build_ok = streams.StreamTests.build_ok
    standard_library = streams.StreamTests.standard_library
    run_native = streams.StreamTests.run_native

    def test_drawing_packet_signed_encoding_alias_reset_and_full_capacity(self):
        self.standard_library()
        self.build_ok('''weave "stdlib/draw.ramos"
fn main() {
let c = draw_new()
let alias = c
draw_line(c,-8192,-1,8192,0,gui_rgb(55,120,220))
print(c.count)
print(gui_number(c.data,0))
for i in 16..32 { stdout(int_to_text(buffer_get(c.data,i)))
stdout(" ") }
stdout("\\n")
draw_reset(alias)
print(c.count)
for i in 0..1024 { draw_pixel(c,i,0,0) }
print(c.count)
print(gui_number(c.data,0))
print(buffer_len(c.data))
draw_reset(c)
print(gui_number(c.data,0))
}''')
        result = self.run_native()
        self.assertEqual((result.returncode,result.stdout),(0,b'1\n1\n0 224 255 255 255 255 255 255 255 255 255 255 255 255 255 255 \n0\n1024\n1024\n49160\n0\n'),result.stderr)

    def test_drawing_rejects_invalid_commands_and_state(self):
        self.standard_library()
        for call in ['draw_rect(c,0,0,0,1,0)','draw_rect(c,0,0,1,-1,0)',
                     'draw_line(c,-8193,0,0,0,0)','draw_line(c,0,0,8193,0,0)',
                     'draw_disk(c,0,0,0,0)','draw_circle(c,0,0,8193,0)',
                     'draw_clear(c,-1)','draw_clear(c,16777216)',
                     'c.count = -1\ndraw_reset(c)', 'c.data = buffer(8)\ndraw_reset(c)',
                     'for i in 0..1025 { draw_pixel(c,0,0,0) }']:
            with self.subTest(call=call):
                self.build_ok('weave "stdlib/draw.ramos"\nfn main() { let c = draw_new()\n'+call+' }')
                result=self.run_native()
                self.assertEqual(result.returncode,1,result.stderr)
                self.assertIn(b'Ramos drawing error',result.stderr)

@unittest.skipIf(BOOTSTRAP or os.name != 'posix', 'requires native GTK')
class LinuxCanvasTests(unittest.TestCase):
    setUp = support.RamosTests.setUp
    build = support.RamosTests.build
    standard_library = streams.StreamTests.standard_library
    setUpClass = classmethod(linux_gui.LinuxGUITests.setUpClass.__func__)
    tearDownClass = classmethod(linux_gui.LinuxGUITests.tearDownClass.__func__)
    gui_build = linux_gui.LinuxGUITests.gui_build
    launch = linux_gui.LinuxGUITests.launch

    def test_native_canvas_repaint_snapshot_clip_resize_replace_and_gc(self):
        self.standard_library()
        self.gui_build((support.ROOT/'tests/fixtures/canvas_probe.ramos').read_text())
        for scale in (1,2):
            with self.subTest(scale=scale):
                previous=self.env
                self.env=dict(previous,GDK_SCALE=str(scale))
                proc=self.launch()
                self.env=previous
                w=self.desktop.window('Ramos Canvas test',proc)
                pixel=lambda x,y:self.desktop.pixel(w,x*scale,y*scale)
                wait(lambda:pixel(25,70)==0xff0000,'snapshot red rectangle')
                wait(lambda:pixel(100,80)==0x0000ff,'blue disk')
                self.assertEqual(pixel(165,80),0xffffff,'outline interior')
                self.assertEqual(pixel(210,70),0,'single pixel')
                self.assertNotEqual(pixel(30,130),0xffffff,'line stroke')
                self.assertTrue(any(pixel(x,65)!=0xffffff for x in (149,150,151)),'box stroke')
                self.assertTrue(any(pixel(x,125)!=0xffffff for x in range(109,114)),'circle stroke')
                self.assertEqual(pixel(5,65),0x0000ff,'negative rectangle clipped')
                self.desktop.resize(w,500*scale,240*scale)
                wait(lambda:pixel(270,70)==0xff0000,'reveal scene after resize/GC')
                self.desktop.click(w,40*scale,25*scale)
                wait(lambda:pixel(25,70)==0x00ff00,'replacement snapshot')
                self.desktop.resize(w,480*scale,240*scale)
                wait(lambda:pixel(270,70)==0x00ff00,'replacement repaint after buffer reset')
                self.desktop.click(w,40*scale,205*scale)
                wait(lambda:pixel(25,70)==0xffffff,'empty scene clears white')
                self.desktop.click(w,130*scale,205*scale)
                wait(lambda:pixel(25,52)==0,'400 full snapshots GC')
                self.desktop.request_close(w)
                out,err=proc.communicate(timeout=10)
                self.assertEqual(proc.returncode,0,err)
                self.assertEqual(out.decode(),EXPECTED)

@unittest.skipIf(BOOTSTRAP or os.name != 'nt','requires native Windows desktop')
class WindowsCanvasTests(unittest.TestCase):
    setUp = support.RamosTests.setUp
    build = support.RamosTests.build
    standard_library = streams.StreamTests.standard_library
    native_path = staticmethod(str)

    def test_native_canvas_repaint_snapshot_clip_resize_replace_and_gc(self):
        self.standard_library()
        result=self.build((support.ROOT/'tests/fixtures/canvas_probe.ramos').read_text(),'--gui','--force')
        self.assertEqual(result.returncode,0,result.stderr)
        report=self.directory/'canvas.json'
        result=subprocess.run([sys.executable,self.native_path(support.ROOT/'tools/canvas_probe.py'),
                               self.native_path(self.output),self.native_path(report)],capture_output=True,timeout=90)
        self.assertEqual(result.returncode,0,(result.stdout,result.stderr,report.read_text() if report.exists() else 'no report'))
        evidence=json.loads(report.read_text())
        self.assertEqual(evidence['stdout'],EXPECTED,evidence)
        self.assertTrue(evidence['closed'] and evidence['gc_stress'],evidence)

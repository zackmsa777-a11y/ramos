"""Theme palette contracts and an actual GTK showcase with live theme changes."""
import os
import json
import subprocess
import sys
import unittest
import test_ramos as support
import test_cli_streams as streams
import test_linux_gui as linux_gui
from test_libraries import BOOTSTRAP
from linux_gui_probe import wait

@unittest.skipIf(BOOTSTRAP, 'seed has no theme library')
class ThemeTests(unittest.TestCase):
    setUp = support.RamosTests.setUp
    build = support.RamosTests.build
    standard_library = streams.StreamTests.standard_library
    run_native = streams.StreamTests.run_native

    def test_theme_palette_and_cards_on_both_native_targets(self):
        self.standard_library()
        r=self.build('''weave "stdlib/theme.ramos"
fn main() {
let paper = theme_paper()
let graphite = theme_graphite()
let ember = theme_ember()
print(paper.name)
print(graphite.name)
print(ember.name)
print(paper.background == gui_rgb(241,245,249))
print(graphite.background == gui_rgb(15,23,42))
print(ember.accent == gui_rgb(251,146,60))
let canvas = draw_new()
theme_card(canvas, ember, gui_rect(16,16,120,80))
print(canvas.count)
print(ember.spacing)
print(ember.control_height)
}''','--force')
        self.assertEqual(r.returncode,0,r.stderr)
        r=self.run_native()
        self.assertEqual((r.returncode,r.stdout),(0,b'Paper\nGraphite\nEmber\ntrue\ntrue\ntrue\n2\n16\n32\n'),r.stderr)

@unittest.skipIf(BOOTSTRAP or os.name!='nt', 'requires genuine native Windows')
class WindowsThemeTests(unittest.TestCase):
    setUp = support.RamosTests.setUp
    build = support.RamosTests.build
    standard_library = streams.StreamTests.standard_library
    native_path = staticmethod(str)

    def test_native_windows_theme_pixels_input_resize_repaint_and_resources(self):
        self.standard_library()
        source=(support.ROOT/'examples/theme_lab.ramos').read_text(encoding='utf-8').replace('../stdlib/','stdlib/')
        r=self.build(source,'--gui','--force');self.assertEqual(r.returncode,0,r.stderr)
        report=self.directory/'theme.json'
        r=subprocess.run([sys.executable,self.native_path(support.ROOT/'tools/canvas_probe.py'),
                          self.native_path(self.output),self.native_path(report),'theme'],capture_output=True,timeout=90)
        self.assertEqual(r.returncode,0,(r.stdout,r.stderr,report.read_text() if report.exists() else 'no report'))
        evidence=json.loads(report.read_text())
        self.assertTrue(evidence['closed'] and evidence['theme_switch'] and evidence['unicode_input'],evidence)

@unittest.skipIf(BOOTSTRAP or os.name!='posix', 'requires native GTK display')
class LinuxThemeTests(unittest.TestCase):
    setUp = support.RamosTests.setUp
    build = support.RamosTests.build
    standard_library = streams.StreamTests.standard_library
    setUpClass = classmethod(linux_gui.LinuxGUITests.setUpClass.__func__)
    tearDownClass = classmethod(linux_gui.LinuxGUITests.tearDownClass.__func__)
    gui_build = linux_gui.LinuxGUITests.gui_build
    launch = linux_gui.LinuxGUITests.launch

    def test_theme_lab_switch_resize_input_and_close(self):
        # Headless CI has no AT-SPI service. Disable its bridge for this pixel
        # test only; the application keeps normal desktop accessibility defaults.
        self.env = dict(self.env, NO_AT_BRIDGE='1')
        self.standard_library()
        self.gui_build((support.ROOT/'examples/theme_lab.ramos').read_text(encoding='utf-8').replace('../stdlib/','stdlib/'))
        proc=self.launch();w=self.desktop.window('Ramos Theme Lab',proc)
        wait(lambda:self.desktop.pixel(w,4,124)==0xf1f5f9,'paper background')
        self.desktop.click(w,640,28)
        wait(lambda:self.desktop.pixel(w,4,124)==0x0f172a,'graphite background')
        self.desktop.click(w,640,28)
        wait(lambda:self.desktop.pixel(w,4,124)==0x18181b,'ember background')
        self.desktop.paste(w,80,62,'Changed مرحبا 🌍')
        self.desktop.resize(w,900,620)
        # Cairo's one-pixel outline is antialiased. Check the transition from
        # surface through border to background rather than an unblended GDI RGB.
        wait(lambda:(self.desktop.pixel(w,881,152)==0x27272a and
                     self.desktop.pixel(w,883,152) not in (0x27272a,0x18181b) and
                     self.desktop.pixel(w,885,152)==0x18181b),'card edge reflows on resize')
        self.desktop.click(w,790,28)
        wait(lambda:self.desktop.pixel(w,4,124)==0xf1f5f9,'paper after resize')
        self.desktop.request_close(w)
        out,err=proc.communicate(timeout=10)
        self.assertEqual((proc.returncode,out,err),(0,b'',b''))

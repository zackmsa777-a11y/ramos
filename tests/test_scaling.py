"""Opt-in scaling, actual GTK setting changes, native placement and resources."""
import json
import os
import shutil
from pathlib import Path
import subprocess
import sys
import unittest
import test_ramos as support
import test_cli_streams as streams
import test_linux_gui as linux_gui
from test_libraries import BOOTSTRAP
from scaling_output import Output
from xsettings_probe import Settings
from linux_gui_probe import wait

@unittest.skipIf(BOOTSTRAP,'retained seed has no new GUI intrinsics')
class ScalingTests(unittest.TestCase):
    setUp=support.RamosTests.setUp
    build=support.RamosTests.build
    build_ok=streams.StreamTests.build_ok
    run_native=streams.StreamTests.run_native

    def test_scaling_private_intrinsic_types(self):
        for call in ['_gui_open_scaled(s"x",320,240)','_gui_open_scaled("x",true,240)',
                     '_gui_open_scaled("x",320)','_gui_dpi(1)']:
            result=self.build('fn main() { print('+call+') }')
            self.assertNotEqual(result.returncode,0)
            self.assertFalse(self.output.exists())

    @unittest.skipUnless(os.name=='posix','static Linux unsupported contract')
    def test_scaling_static_linux_is_fallible(self):
        self.build_ok('fn main() { print(_gui_open_scaled("x",320,240))\nprint(io_error())\nprint(_gui_dpi())\nprint(io_error()) }')
        result=self.run_native()
        self.assertEqual((result.returncode,result.stdout),(0,b'-38\n-38\n-38\n-38\n'),result.stderr)

@unittest.skipIf(BOOTSTRAP or os.name!='posix','requires real GTK on isolated Xvfb')
class LinuxScalingTests(unittest.TestCase):
    setUp=support.RamosTests.setUp
    build=support.RamosTests.build
    standard_library=streams.StreamTests.standard_library
    gui_build=linux_gui.LinuxGUITests.gui_build
    setUpClass=classmethod(linux_gui.LinuxGUITests.setUpClass.__func__)
    tearDownClass=classmethod(linux_gui.LinuxGUITests.tearDownClass.__func__)

    def test_genuine_gtk_scale_change_pixels_events_aliases_and_churn(self):
        self.standard_library()
        self.gui_build((support.ROOT/'tests/fixtures/scaling_probe.ramos').read_text(encoding='utf-8'))
        settings=Settings(self.desktop)
        self.addCleanup(settings.close)
        env=dict(self.env,NO_AT_BRIDGE='1');env.pop('GDK_SCALE',None)
        proc=subprocess.Popen([str(self.output)],env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        def cleanup():
            if proc.poll() is None:proc.kill()
            proc.wait(timeout=5)
            proc.stdout.close();proc.stderr.close()
        self.addCleanup(cleanup)
        output=Output(proc)
        self.assertEqual([output.line() for _ in range(3)],['-9','-22','-16'])
        w=self.desktop.window('Ramos Scaling test',proc)
        wait(lambda:self.desktop.pixel(w,30,95)==0x2850dc,'initial native panel')
        wait(lambda:self.desktop.pixel(w,140,95)==0xdc3c28,'initial native canvas')
        # Toolkit settings actually change the native widget scale and device pixels.
        settings.set_scale(2)
        line=output.line()
        self.assertEqual(line.split()[:2],['scale','192'],line)
        self.assertTrue(all(int(v)>0 for v in line.split()[2:]),line)
        wait(lambda:self.desktop.pixel(w,60,190)==0x2850dc,'2x panel and retained geometry')
        wait(lambda:self.desktop.pixel(w,280,190)==0xdc3c28,'2x native canvas')
        baseline = None
        def resources():
            process = Path('/proc')/str(proc.pid)
            pages = int((process/'statm').read_text().split()[1])
            return (len(list((process/'fd').iterdir())),pages*os.sysconf('SC_PAGE_SIZE'))
        for i in range(200):
            self.desktop.command("windowfocus",w,"mousemove","--window",w,100,330,"click","1")
            parts=output.line().split()
            self.assertEqual(parts[:2],['step',str(i)])
            self.assertLess(int(parts[2]),262144)
            if i == 9: baseline = resources()
        after = resources()
        self.assertLessEqual(after[0], baseline[0]+2)
        self.assertLessEqual(after[1], baseline[1]+8*1048576)
        settings.set_scale(1)
        line=output.line();self.assertEqual(line.split()[:2],['scale','96'],line)
        wait(lambda:self.desktop.pixel(w,30,95)==0x2850dc,'1x panel restored')
        wait(lambda:self.desktop.pixel(w,140,95)==0xdc3c28,'1x canvas restored')
        self.desktop.request_close(w)
        self.assertEqual(output.line(),'-9')
        self.assertEqual(output.line(),'true')
        self.assertEqual(proc.wait(timeout=5),0,proc.stderr.read())
        self.assertEqual(proc.stderr.read(),b'')
        report = {'genuine_gtk_scale_sequence':[96,192,96],
                  'native_panel_canvas_pixels':True,'retained_geometry_alias_safe':True,
                  'churn_steps':200,'churn_bytes':200*1048576,
                  'managed_live_limit_checked':262144,
                  'resources_warm':{'file_descriptors':baseline[0],'rss_bytes':baseline[1]},
                  'resources_after':{'file_descriptors':after[0],'rss_bytes':after[1]},
                  'closed':True,'scope':'Bounded native GTK churn; no Windows or hours-long soak claim.'}
        (support.ROOT/'build/linux-scaling-proof.json').write_text(json.dumps(report,indent=2)+'\n')

@unittest.skipIf(BOOTSTRAP or os.name!='nt','requires native Windows display')
class WindowsScalingTests(unittest.TestCase):
    setUp=support.RamosTests.setUp
    build=support.RamosTests.build
    standard_library=streams.StreamTests.standard_library
    native_path=staticmethod(str)

    def test_native_scaling_awareness_geometry_font_lifetimes_and_resources(self):
        self.standard_library()
        result=self.build((support.ROOT/'tests/fixtures/scaling_probe.ramos').read_text(encoding='utf-8'),'--gui','--force')
        self.assertEqual(result.returncode,0,result.stderr)
        report=self.directory/'scaling.json'
        result=subprocess.run([sys.executable,self.native_path(support.ROOT/'tools/scaling_probe.py'),
                               self.native_path(self.output),self.native_path(report)],capture_output=True,timeout=100)
        self.assertEqual(result.returncode,0,(result.stdout,result.stderr,report.read_text(encoding='utf-8') if report.exists() else 'no report'))
        evidence=json.loads(report.read_text(encoding='utf-8'))
        self.assertTrue(evidence['closed'] and evidence['thread_context_restored'])
        self.assertEqual(evidence['churn_steps'],200)
        self.assertEqual(evidence['reopen_cycles'],20)
        shutil.copyfile(report,support.ROOT/'build/windows-scaling-proof.json')

    def test_native_scaling_demo_full_canvas_pixels(self):
        # Dense stroke/edge comparison complements the flat-color pixel probes.
        # No DPI change is generated; real transitions still need the desktop test.
        import ctypes as C
        from ctypes import wintypes as W
        import time
        from canvas_capture import capture
        self.standard_library()
        code=(support.ROOT/'examples/scaling.ramos').read_text(encoding='utf-8')
        result=self.build(code.replace('../stdlib/','stdlib/'),'--gui','--force')
        self.assertEqual(result.returncode,0,result.stderr)
        proc=subprocess.Popen([str(self.output)],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        def cleanup():
            if proc.poll() is None:proc.kill()
            proc.wait(timeout=5);proc.stdout.close();proc.stderr.close()
        self.addCleanup(cleanup)
        output=Output(proc)
        self.assertTrue(output.line().startswith('DPI '))
        # The status is printed before the event loop dispatches initial paints.
        time.sleep(.5)
        evidence=capture(proc.pid,self.directory/'canvas')
        self.assertEqual(evidence['before_different_pixels'],0,evidence)
        self.assertEqual(evidence['after_redraw_different_pixels'],0,evidence)
        self.assertEqual(evidence['changed_by_redraw_pixels'],0,evidence)
        user=C.WinDLL('user32')
        user.PostMessageW.argtypes=[W.HWND,W.UINT,W.WPARAM,W.LPARAM]
        user.PostMessageW.restype=W.BOOL
        self.assertTrue(user.PostMessageW(evidence['window_handle'],0x10,0,0))
        self.assertEqual(output.line(),'closed -9')
        self.assertEqual(proc.wait(timeout=10),0,proc.stderr.read())
        self.assertEqual(proc.stderr.read(),b'')
        (support.ROOT/'build/windows-canvas-proof.json').write_text(json.dumps(evidence,indent=2)+'\n',encoding='utf-8')

"""Actual GTK desktop acceptance, plus ELF imports and headless error contracts."""
import os
from pathlib import Path
import selectors
import shutil
import struct
import subprocess
import sys
import time
import unittest
import test_ramos as support
from test_libraries import BOOTSTRAP
import test_cli_streams as streams
sys.path.insert(0, str(support.ROOT / 'tools'))
from linux_gui_probe import Desktop, wait

@unittest.skipIf(BOOTSTRAP or os.name != 'posix', 'requires self-hosted Linux compiler')
class LinuxGUITests(unittest.TestCase):
    setUp = support.RamosTests.setUp
    build = support.RamosTests.build
    standard_library = streams.StreamTests.standard_library

    @classmethod
    def setUpClass(cls):
        missing = [n for n in ('Xvfb','xdotool','xclip') if not shutil.which(n)]
        if missing: raise unittest.SkipTest('Linux GUI test tools missing: '+', '.join(missing))
        read, write = os.pipe()
        cls.server = subprocess.Popen(['Xvfb','-displayfd',str(write),'-screen','0','1280x900x24','-nolisten','tcp'],
                                      pass_fds=(write,), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        os.close(write)
        with selectors.DefaultSelector() as sel:
            sel.register(read, selectors.EVENT_READ)
            if not sel.select(5):
                cls.server.kill(); cls.server.wait(); os.close(read)
                raise RuntimeError('Xvfb startup timed out')
        number = os.read(read, 64).strip().decode(); os.close(read)
        cls.env = dict(os.environ, DISPLAY=':'+number, GDK_BACKEND='x11', LC_ALL='C.UTF-8')
        cls.desktop = Desktop(cls.env)

    @classmethod
    def tearDownClass(cls):
        cls.desktop.close(); cls.server.terminate(); cls.server.wait(timeout=5)

    def gui_build(self, source):
        result = self.build(source, '--gui', '--force')
        self.assertEqual(result.returncode, 0, result.stderr)

    def launch(self):
        proc = subprocess.Popen([str(self.output)], cwd=self.directory, env=self.env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        def cleanup():
            if proc.poll() is None: proc.kill()
            proc.communicate(timeout=5)
        self.addCleanup(cleanup)
        return proc

    def test_dynamic_elf_and_no_display_status(self):
        self.gui_build('fn main() { print(_gui_open("no display",320,240))\nprint(io_error())\nprint(_gui_close()) }')
        binary = self.output.read_bytes()
        h = struct.unpack_from('<16sHHIQQQIHHHHHH', binary)
        segments = [struct.unpack_from('<IIQQQQQQ',binary,h[5]+i*h[9]) for i in range(h[10])]
        self.assertEqual(h[10],7)
        self.assertEqual([s[0] for s in segments], [6,3,1,1,1,2,0x6474e551])
        self.assertEqual(binary[segments[1][2]:segments[1][2]+segments[1][5]], b'/lib64/ld-linux-x86-64.so.2\0')
        for s in segments:
            if s[0]==1:
                self.assertFalse(s[1]&3==3)
                self.assertLessEqual(s[2]+s[5],len(binary))
                self.assertEqual(s[2]%s[7],s[3]%s[7])
        self.assertIn(b'libgtk-3.so.0\0',binary)
        env=dict(self.env,DISPLAY=':65534',WAYLAND_DISPLAY='ramos-missing')
        result=subprocess.run([str(self.output)],env=env,capture_output=True,timeout=5)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(result.stdout,b'-19\n-19\n0\n')

    def test_validation_lifetime_and_queue_overflow(self):
        self.standard_library()
        self.gui_build('''weave "stdlib/gui.ramos"
fn main() {
print(_gui_open("x",-1,240))
print(buffer_len(_gui_poll(-2)))
print(io_error())
var i = 0
while i < 12 {
gui_check(gui_open(s"Lifecycle",320,240))
gui_input(1,10,10,200,28,s"مرحبا 🌍")
print(gui_text(1))
gui_check(gui_close())
i += 1
}
gui_check(gui_open(s"Lifecycle",320,240))
gui_label(1,0,0,200,24,s"label")
gui_button(2,0,30,100,32,s"button")
gui_editor(3,0,70,200,100,s"editor")
print(gui_text(1))
print(gui_text(2))
print(gui_text(3))
print(_gui_open("second",320,240))
print(_gui_control(gui_properties(2,2,0,0,100,30,0),"duplicate"))
print(_gui_control(gui_properties(1,65,0,0,100,30,0),"bad"))
print(_gui_control(gui_properties(7,1,0,0,0,30,0),""))
let bad = buffer(1)
buffer_set(bad,0,255)
print(_gui_control(gui_properties(6,1,0,0,0,0,0),bad))
print(_gui_control(gui_properties(6,1,0,0,0,0,0),"x\\0"))
i = 0
while i < 40 { let b = buffer(1048576)
buffer_set(b,0,i)
i += 1 }
collect()
print(gui_text(3))
gui_set(3,s"after GC 🌍")
print(gui_text(3))
while gui_event(0).kind != 0 {}
let timed = gui_event(40)
print(timed.kind)
i = 0
while i < 70 { gui_set(3,s"x")
i += 1 }
let packet = _gui_poll(0)
print(buffer_len(packet))
print(io_error())
gui_check(gui_close())
print(buffer_len(_gui_text(1)))
print(io_error())
print(_gui_close())
}''')
        try: result=subprocess.run([str(self.output)],env=self.env,capture_output=True,timeout=10)
        except subprocess.TimeoutExpired as e:
            self.fail(f'Native timeout: stdout={e.stdout!r}, stderr={e.stderr!r}')
        self.assertEqual(result.returncode,0,result.stderr)
        expected=b'-22\n0\n-22\n'+('مرحبا 🌍\n'*12).encode()+b'label\nbutton\neditor\n-16\n-17\n-9\n-22\n-22\n-22\neditor\n'+ 'after GC 🌍\n'.encode()+b'0\n0\n-75\n0\n-9\n0\n'
        self.assertEqual(result.stdout,expected)

    def test_notes_unicode_save_overwrite_clear_resize_and_close(self):
        self.standard_library()
        source=(support.ROOT/'examples/notes.ramos').read_text().replace('../stdlib/','stdlib/')
        self.gui_build(source)
        proc=self.launch(); w=self.desktop.window('Ramos Notes')
        wait(lambda:self.desktop.pixel(w,2,2)==0x3778dc,'painted colored panel')
        path=self.directory/'note-🌍.txt'; content='مرحبا 🌍\nNative Linux Notes'
        self.desktop.paste(w,200,65,str(path)); self.desktop.paste(w,200,150,content)
        self.desktop.command('key','End','BackSpace','s')
        self.desktop.click(w,65,400)
        wait(path.exists,'saved file'); self.assertEqual(path.read_text(),content)
        self.desktop.paste(w,200,150,'replacement')
        self.desktop.click(w,65,400); self.assertEqual(path.read_text(),content)
        self.desktop.resize(w,800,600)
        empty=self.directory/'empty.txt'; self.desktop.paste(w,200,65,str(empty))
        self.desktop.click(w,180,560); self.desktop.click(w,65,560)
        wait(empty.exists,'clear and save after resize'); self.assertEqual(empty.read_bytes(),b'')
        self.desktop.resize(w,300,180); self.desktop.resize(w,640,440)
        self.desktop.request_close(w)
        stdout,stderr=proc.communicate(timeout=5)
        self.assertEqual(proc.returncode,0,stderr); self.assertEqual(stdout,b'')

    def test_cleanup_on_return_exit_and_arithmetic_trap(self):
        self.standard_library()
        for action,code in [('return',0),('exit(7)',7),('let n = 9223372036854775807\nprint(n+1)',1)]:
            self.gui_build('''weave "stdlib/gui.ramos"
fn main() {
gui_check(gui_open(s"Cleanup",320,240))
gui_button(1,10,10,100,32,s"Finish")
while gui_event(-1).kind != 2 {}
'''+action+'\n}')
            proc=self.launch();w=self.desktop.window('Cleanup'); self.desktop.click(w,40,25)
            stdout,stderr=proc.communicate(timeout=5)
            self.assertEqual(proc.returncode,code,stderr)
            if code==1:self.assertIn(b'arithmetic overflow',stderr)
            self.assertFalse(subprocess.run(['xdotool','search','--onlyvisible','--name','^Cleanup$'],env=self.env,capture_output=True).stdout)

    def test_run_gui_real_window_and_temporary_cleanup(self):
        self.standard_library()
        source=(support.ROOT/'examples/gui_hello.ramos').read_text().replace('../stdlib/','stdlib/')
        self.source.write_text(source)
        temp=self.directory/'temp'; temp.mkdir()
        env=dict(self.env,TMPDIR=str(temp))
        proc=subprocess.Popen([str(support.COMPILER),'run',str(self.source),'--gui'],env=env,
                              cwd=self.directory,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        self.addCleanup(lambda: proc.kill() if proc.poll() is None else None)
        w=self.desktop.window('Hello, Ramos')
        self.desktop.request_close(w)
        stdout,stderr=proc.communicate(timeout=5)
        self.assertEqual(proc.returncode,0,stderr)
        self.assertEqual(stdout,b'')
        self.assertEqual(list(temp.iterdir()),[])
        self.assertFalse(self.output.exists())

    def picker(self, title, path=None):
        window=self.desktop.window(title)
        if path is None:
            self.desktop.command('windowfocus',window,'key','Escape')
        else:
            self.desktop.command('windowfocus',window,'key','ctrl+l')
            time.sleep(.15)
            self.desktop.command('key','ctrl+a')
            subprocess.run(['xclip','-selection','clipboard'],input=str(path).encode(),env=self.env,
                           check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=5)
            self.desktop.command('key','ctrl+v')
            time.sleep(.2)
            self.desktop.command('key','Return')
        wait(lambda: not subprocess.run(['xdotool','search','--onlyvisible','--name','^'+title+'$'],
                                        env=self.env,capture_output=True).stdout,'dialog dismissal')

    def test_native_file_picker_open_save_cancel_validation_and_no_file_write(self):
        self.standard_library()
        existing=self.directory/'existing-مرحبا 🌍.txt';existing.write_text('original')
        destination=self.directory/'new-مرحبا 🌍.txt'
        self.gui_build('''weave "stdlib/gui.ramos"
fn main() {
gui_check(gui_open(s"Pickers",320,240))
let before = cwd()
let bad = buffer(1)
buffer_set(bad,0,255)
print(buffer_len(_gui_choose("x","",2)))
print(io_error())
print(buffer_len(_gui_choose(bad,"",0)))
print(io_error())
let cancelled = gui_open_file(s"Cancel picker",s"")
print(cancelled.status)
print(cancelled.path)
let opened = gui_open_file(s"Open picker",s"")
print(opened.status)
print(opened.path)
collect()
let saved = gui_save_file(s"Save picker",s"suggested.txt")
print(saved.status)
print(saved.path)
print(buffer_len(read_file(to_bytes(saved.path))))
print(io_error())
print(gui_choose_file(s"bad",s"",-1).status)
print(string(cwd()) == string(before))
gui_check(gui_close())
}''')
        proc=self.launch()
        self.picker('Cancel picker')
        self.picker('Open picker',existing)
        self.picker('Save picker',destination)
        out,err=proc.communicate(timeout=5)
        self.assertEqual(proc.returncode,0,err)
        self.assertEqual(out,('0\n-22\n0\n-22\n1\n\n0\n'+str(existing)+'\n0\n'+str(destination)+'\n0\n-2\n-22\ntrue\n').encode())
        self.assertEqual(existing.read_text(),'original')
        self.assertFalse(destination.exists())

    def test_notes_open_save_as_cancel_and_invalid_text_preservation(self):
        self.standard_library()
        existing=self.directory/'source-مرحبا 🌍.txt'; content='First\nمرحبا 🌍'
        existing.write_text(content)
        invalid=self.directory/'invalid.txt';invalid.write_bytes(b'bad\xff')
        destination=self.directory/'saved-مرحبا 🌍.txt'
        self.gui_build((support.ROOT/'examples/notes.ramos').read_text().replace('../stdlib/','stdlib/'))
        proc=self.launch();window=self.desktop.window('Ramos Notes')
        wait(lambda:self.desktop.pixel(window,2,2)==0x3778dc,'Notes painting')
        self.desktop.click(window,450,32);self.picker('Open a note',existing)
        self.desktop.click(window,550,32);self.picker('Save a new note')
        self.assertFalse(destination.exists())
        self.desktop.click(window,450,32);self.picker('Open a note',invalid)
        self.desktop.click(window,550,32);self.picker('Save a new note',destination)
        wait(destination.exists,'save after invalid Open')
        self.assertEqual(destination.read_text(),content)
        self.assertEqual(existing.read_text(),content)
        self.desktop.click(window,550,32);self.picker('Save a new note',existing)
        self.assertEqual(existing.read_text(),content)
        self.desktop.resize(window,800,600)
        self.desktop.click(window,610,32);self.picker('Open a note')
        self.desktop.request_close(window)
        out,err=proc.communicate(timeout=5)
        self.assertEqual(proc.returncode,0,err)

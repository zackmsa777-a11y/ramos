"""Test a compiler + library bundle from a fresh Unicode path with empty PATH."""
import argparse,hashlib,json,os,shutil,subprocess,tempfile,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compiler',required=True,type=Path)
    parser.add_argument('--package',type=Path,help='test the actual published ZIP when supplied')
    parser.add_argument('--output',type=Path,default=ROOT/'build/package-proof.json')
    args=parser.parse_args()
    compiler=args.compiler.resolve()
    native_name='ramos.exe' if os.name=='nt' else 'ramos-linux-x86_64'
    with tempfile.TemporaryDirectory(prefix='Ramos package ') as temporary:
        home=Path(temporary)/'clean install مرحبا';home.mkdir()
        if args.package:
            with zipfile.ZipFile(args.package) as archive:archive.extractall(home)
        else:
            for folder in ('stdlib','examples'):shutil.copytree(ROOT/folder,home/folder)
            shutil.copyfile(compiler,home/native_name)
        installed=home/native_name;installed.chmod(0o755)
        assert installed.read_bytes()==compiler.read_bytes(),'Unexpected packaged compiler'
        env=dict(os.environ,PATH='')
        def run(*command,input=None,code=0,expected=None):
            result=subprocess.run([str(x) for x in command],cwd=home,env=env,
                                  capture_output=True,input=input,timeout=30)
            assert result.returncode==code,(command,result.returncode,result.stdout,result.stderr)
            assert not result.stderr,(command,result.stderr)
            if expected is not None:assert result.stdout==expected,(command,result.stdout,expected)
            return result
        version=run(installed,'--version').stdout.decode().strip()
        source=home/'hello source.ramos'
        source.write_text('fn main() { print(s"Hello مرحبا")\nprint(arg(1))\nexit(7) }\n',encoding='utf-8')
        run(installed,'run',source,'--','argument 🌍',code=7,
            expected='Hello مرحبا\nargument 🌍\n'.encode())
        sort=home/('sort.exe' if os.name=='nt' else 'sort')
        run(installed,'build','examples/rsort.ramos','-o',sort)
        run(sort,input=b'9\n-2\n9\n0\n',expected=b'-2\n0\n9\n9\n')
        run(sort,input=b'',expected=b'')
        # Executables need no compiler or stdlib at runtime.
        installed.unlink();shutil.rmtree(home/'stdlib')
        run(sort,input=b'3\n1\n2',expected=b'1\n2\n3\n')
        report={'version':version,'target':'windows-x64' if os.name=='nt' else 'linux-x64',
            'compiler_sha256':hashlib.sha256(compiler.read_bytes()).hexdigest(),
            'unicode_install_path':True,'empty_path':True,'run_arguments_exit_status':True,
            'library_build_and_sort':True,'executable_runs_without_compiler_or_sources':True,
            'checks':5,'package_sha256':hashlib.sha256(args.package.read_bytes()).hexdigest() if args.package else None,
            'scope':'Native CLI packaging; desktop and terminal interactions have separate native tests.'}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
if __name__=='__main__':main()

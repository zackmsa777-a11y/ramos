#!/usr/bin/env python3
"""Measure equivalent checked while/for loops; a single workload, not a language index."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import random
import statistics
import subprocess
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compiler',type=Path,default=ROOT/'ramos')
    parser.add_argument('--output',type=Path,default=ROOT/'build/range-timing.json')
    parser.add_argument('--samples',type=int,default=17)
    parser.add_argument('--count',type=int,default=5000000)
    args=parser.parse_args()
    if platform.system()!='Linux' or args.samples<5 or not 1<=args.count<=2147483647:
        parser.error('use Linux, at least five samples and a count in 1..2147483647')
    compiler=args.compiler.resolve();cpu=min(os.sched_getaffinity(0));os.sched_setaffinity(0,{cpu})
    digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    sources={name:ROOT/'benchmarks/0.14.0/range'/f'{name}.ramos' for name in ['while','for']}
    times={name:[] for name in sources};orders=[];rng=random.Random(14004)
    with tempfile.TemporaryDirectory() as tmp:
        outputs={name:Path(tmp)/name for name in sources}
        for name,source in sources.items():
            subprocess.run([str(compiler),'build',str(source),'-o',str(outputs[name])],check=True,capture_output=True)
            for count in [-1,0,1,7,args.count]:
                result=subprocess.run([str(outputs[name]),str(count)],check=True,capture_output=True)
                positive=max(0,count)
                assert result.stdout==f'{positive*(positive-1)//2}\n'.encode()
        for trial in range(args.samples+2):
            order=list(sources);rng.shuffle(order)
            if trial>=2:orders.append(order)
            for name in order:
                start=time.perf_counter_ns()
                result=subprocess.run([str(outputs[name]),str(args.count)],check=True,capture_output=True)
                elapsed=time.perf_counter_ns()-start
                assert result.stdout==f'{args.count*(args.count-1)//2}\n'.encode()
                if trial>=2:times[name].append(elapsed)
        report={'compiler_version':subprocess.check_output([str(compiler),'--version'],text=True).strip(),
                'compiler_sha256':digest(compiler),'pinned_cpu':cpu,'work_count':args.count,
                'sources_sha256':{name:digest(source) for name,source in sources.items()},
                'binaries_sha256':{name:digest(path) for name,path in outputs.items()},
                'samples_ns':times,'median_ns':{name:statistics.median(values) for name,values in times.items()},
                'orders':orders,'warmups':2,'random_seed':14004,
                'meaning':'Equivalent checked sum loops on a shared VM. Startup included; no general speedup or language ranking.'}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2)+'\n')
    print(report['median_ns'])


if __name__=='__main__':main()

"""Local HTTP/TLS fixtures only. Never used by a Ramos application."""
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import os
from pathlib import Path
import shutil
import ssl
import subprocess
import threading
import time

class Fixture:
    def __init__(self,directory,tls=False):
        self.directory=Path(directory);self.servers=[];self.threads=[];self.requests=[];self.trusted_thumbprint=None
        self.responses=[]
        owner=self
        class Handler(BaseHTTPRequestHandler):
            def handle(self):
                try:super().handle()
                except (BrokenPipeError,ConnectionResetError,ssl.SSLError):pass
            protocol_version='HTTP/1.1'
            def request(self):
                body=self.rfile.read(int(self.headers.get('Content-Length','0')))
                owner.requests.append((self.command,self.path,dict(self.headers),body))
                status=200;data=b'hello\0world\xff'
                if self.path=='/chat' and owner.responses:
                    index=min(len(owner.requests)-1,len(owner.responses)-1)
                    status,data=owner.responses[index]
                if self.path.startswith('/echo'):data=body
                if self.path=='/auth':status=401;data=b'{"error":"unauthorized"}'
                if self.path=='/empty':status=204;data=b''
                if self.path=='/redirect':status=302;data=b'redirect'
                if self.path=='/large':data=b'x'*1048569
                if self.path=='/exact':data=b'x'*1048568
                if self.path=='/slow':time.sleep(.6);data=b'late'
                if self.path=='/stall':time.sleep(2.5);data=b'late'
                if self.path=='/chunked':
                    self.send_response(200);self.send_header('Transfer-Encoding','chunked');self.end_headers()
                    self.wfile.write(b'3\r\nabc\r\n2\r\nde\r\n0\r\n\r\n');return
                self.send_response(status)
                if status==302:self.send_header('Location','/echo')
                self.send_header('Content-Length',str(len(data)));self.end_headers()
                try:self.wfile.write(data)
                except (BrokenPipeError,ConnectionResetError,ssl.SSLError):pass
            do_GET=request;do_POST=request
            def log_message(self,*args):pass
        self.handler=Handler
        self.http=self.server()
        self.https=None;self.untrusted=None
        if tls:
            try:self.certificates()
            except Exception:self.close();raise
    def server(self,cert=None,key=None):
        server=ThreadingHTTPServer(('127.0.0.1',0),self.handler);server.daemon_threads=True
        if cert:
            context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);context.minimum_version=ssl.TLSVersion.TLSv1_2
            context.load_cert_chain(cert,key);server.socket=context.wrap_socket(server.socket,server_side=True)
        thread=threading.Thread(target=lambda:server.serve_forever(poll_interval=.02),daemon=True);thread.start()
        self.servers.append(server);self.threads.append(thread)
        return server
    def url(self,path='/',server=None,host='127.0.0.1'):
        target=server or self.http;scheme='http' if target is self.http else 'https'
        return f'{scheme}://{host}:{target.server_port}{path}'
    def certificates(self):
        binary=shutil.which('openssl')
        if not binary and os.name=='nt':
            candidate=Path(os.environ.get('ProgramFiles','C:/Program Files'))/'Git/usr/bin/openssl.exe'
            if candidate.is_file():binary=str(candidate)
        assert binary,'OpenSSL test tooling is required for controlled TLS acceptance'
        def openssl(*args):
            subprocess.run([binary,*args],cwd=self.directory,check=True,capture_output=True,timeout=30)
        openssl('req','-x509','-newkey','rsa:2048','-nodes','-keyout','root.key','-out','root.pem','-days','2','-subj','/CN=Ramos temporary TLS fixture','-addext','basicConstraints=critical,CA:TRUE','-addext','keyUsage=critical,keyCertSign,cRLSign')
        openssl('req','-new','-newkey','rsa:2048','-nodes','-keyout','leaf.key','-out','leaf.csr','-subj','/CN=localhost')
        (self.directory/'leaf.ext').write_text('subjectAltName=DNS:localhost\nbasicConstraints=critical,CA:FALSE\nkeyUsage=critical,digitalSignature,keyEncipherment\nextendedKeyUsage=serverAuth\n')
        openssl('x509','-req','-in','leaf.csr','-CA','root.pem','-CAkey','root.key','-CAcreateserial','-out','leaf.pem','-days','2','-extfile','leaf.ext')
        openssl('req','-x509','-newkey','rsa:2048','-nodes','-keyout','untrusted.key','-out','untrusted.pem','-days','2','-subj','/CN=localhost','-addext','subjectAltName=DNS:localhost')
        self.https=self.server(self.directory/'leaf.pem',self.directory/'leaf.key')
        self.untrusted=self.server(self.directory/'untrusted.pem',self.directory/'untrusted.key')
        if os.name=='nt':
            openssl('x509','-in','root.pem','-outform','DER','-out','root.cer')
            thumb=hashlib.sha1((self.directory/'root.cer').read_bytes()).hexdigest()
            self.trusted_thumbprint=thumb
            subprocess.run(['certutil','-f','-addstore','Root',str(self.directory/'root.cer')],check=True,capture_output=True,timeout=30)
    def env(self):
        env=dict(os.environ)
        if self.https and os.name!='nt':env['SSL_CERT_FILE']=str(self.directory/'root.pem')
        return env
    def close(self):
        for server in self.servers:server.shutdown();server.server_close()
        for thread in self.threads:thread.join(timeout=5)
        if self.trusted_thumbprint:
            subprocess.run(['certutil','-delstore','Root',self.trusted_thumbprint],check=True,capture_output=True,timeout=30)
            self.trusted_thumbprint=None

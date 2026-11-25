"""Trusted startup probes executed in exactly the same sandbox as user code."""


def resource_probe(limits):
    return f'''
import os, errno, json, time, subprocess, socket, sys
from pathlib import Path
from importlib.metadata import version
from io import StringIO
from Bio import SeqIO
from rdkit import Chem
from rdkit.Chem import Descriptors, Draw, rdFingerprintGenerator
import numpy, pandas, scipy, matplotlib, PIL
assert sys.version_info[:2] == (3, 12)
c = Path('/sys/fs/cgroup')
assert int((c/'memory.max').read_text()) == {limits.memory}
assert int((c/'memory.swap.max').read_text()) == 0
assert int((c/'pids.max').read_text()) == {limits.pids}
quota, period = map(int, (c/'cpu.max').read_text().split())
assert quota / period == {limits.cpus / 1_000_000_000}
status = Path('/proc/self/status').read_text()
assert 'NoNewPrivs:\\t1' in status and 'Seccomp:\\t2' in status
assert 'CapEff:\\t0000000000000000' in status and os.getuid() == 10001
assert not Path('/var/run/docker.sock').exists()
assert not Path('/home/xiaoruiwang').exists()
try:
    Path('/root-write-test').write_text('x')
    raise AssertionError('rootfs writable')
except OSError as e:
    assert e.errno in (errno.EROFS, errno.EACCES)
for address, port in [('1.1.1.1',80), ('10.0.0.1',80), ('169.254.169.254',80),
                      ('127.0.0.1',8091), ('172.17.0.1',8080)]:
    s = socket.socket(); s.settimeout(.2)
    try:
        s.connect((address, port))
        raise AssertionError('network enabled')
    except OSError:
        pass
    finally:
        s.close()
v = os.statvfs('/work')
assert v.f_blocks * v.f_frsize <= {limits.workspace}
try:
    with open('/work/fill', 'wb') as f:
        for _ in range({limits.workspace // (1024 * 1024) + 1}): f.write(b'x' * (1024 * 1024))
    raise AssertionError('tmpfs unlimited')
except OSError as e:
    assert e.errno == errno.ENOSPC
finally:
    Path('/work/fill').unlink(missing_ok=True)
children=[]
try:
    for _ in range({limits.pids + 1}):
        pid=os.fork()
        if pid == 0:
            time.sleep(10); os._exit(0)
        children.append(pid)
    raise AssertionError('pids unlimited')
except OSError as e:
    assert e.errno == errno.EAGAIN and 1 <= len(children) < {limits.pids}
finally:
    for pid in children: os.kill(pid, 9)
    for pid in children: os.waitpid(pid, 0)
def stat(): return dict(line.split() for line in (c/'cpu.stat').read_text().splitlines())
before=stat()
workers=[subprocess.Popen([sys.executable, '-c', 'import time; t=time.monotonic()+2\\nwhile time.monotonic()<t: pass']) for _ in range(4)]
for worker in workers: assert worker.wait() == 0
assert int(stat()['nr_throttled']) > int(before['nr_throttled'])
seq=list(SeqIO.parse(StringIO('>one\\nMKWVTF\\n'), 'fasta'))[0]
assert len(seq) == 6
mol=Chem.MolFromSmiles('CCO')
assert round(Descriptors.MolWt(mol), 2) == 46.07
assert rdFingerprintGenerator.GetMorganGenerator(radius=2).GetFingerprint(mol).GetNumBits() == 2048
Draw.MolToFile(mol, str(output_dir/'molecule.png'))
pandas.DataFrame([{{'length':len(seq)}}]).to_csv(output_dir/'sequence.csv', index=False)
result={{'versions':{{name:version(name) for name in ['biopython','rdkit','numpy','pandas','scipy','matplotlib','Pillow']}}, 'python':sys.version}}
'''

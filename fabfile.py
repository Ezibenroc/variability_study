from invoke import task
import os

OPENBLAS_ARCHIVE   = 'openblas.zip'
OPENBLAS_DIRECTORY = 'OpenBLAS-0.2.20'
OPENBLAS_URL       = 'https://github.com/xianyi/OpenBLAS/archive/v0.2.20.zip'
EXP_DIRECTORY      = 'variability_study'
EXP_ARCHIVE        = EXP_DIRECTORY + '.zip'

APT_PACKAGES = [
        'build-essential',
        'python',
        'python3',
        'python-dev',
        'python3-dev',
        'zip',
        'linux-cpupower',
        'make',
        'linux-tools',
        'git',
        'numactl',
        'likwid',
        'time',
        'cpufrequtils',
        'hwloc',
    ]
PIP_PACKAGES = [
        'psutil',
        'py-cpuinfo',
        'GitPython',
        'pandas',
        'lxml',
    ]

@task
def get_openblas_archive(ctx):
    if not os.path.isfile(OPENBLAS_ARCHIVE):
        ctx.local('wget %s -O %s' % (OPENBLAS_URL, OPENBLAS_ARCHIVE))

@task
def clean(ctx):
    ctx.run('rm -rf ~/* /usr/lib/openblas-base /usr/lib/libopenblas.so')
    ctx.run('yes | pip3 uninstall %s' % ' '.join(PIP_PACKAGES))
    ctx.run('yes | apt remove %s' % ' '.join(APT_PACKAGES))

@task
def copy_archives(ctx):
    ctx.put('openblas.zip', 'openblas.zip')
    ctx.put(EXP_ARCHIVE, EXP_ARCHIVE)

@task
def install_apt_packages(ctx):
    ctx.run('yes | apt upgrade')
    ctx.run('yes | apt install %s' % ' '.join(APT_PACKAGES))

@task
def install_openblas(ctx):
    ctx.run('unzip %s' % OPENBLAS_ARCHIVE)
    with ctx.cd(OPENBLAS_DIRECTORY):
        ctx.run('make -j 8')
        ctx.run('make install PREFIX=/usr')
    ctx.run('mkdir /usr/lib/openblas-base/')
    ctx.run('ln -s /usr/lib/libopenblas.so /usr/lib/openblas-base/libblas.so')

@task
def install_pip_packages(ctx):
    ctx.run('wget https://bootstrap.pypa.io/get-pip.py')
    ctx.run('python3 get-pip.py')
    ctx.run('pip3 install %s' % ' '.join(PIP_PACKAGES))

@task
def setup_os(ctx):
    ctx.run('modprobe msr')

@task
def extract_experiment(ctx):
    ctx.run('unzip %s' % EXP_ARCHIVE)

@task
def test_installation(ctx):
    with ctx.cd(EXP_DIRECTORY):
        ctx.run('python3 ./runner.py --csv_file /tmp/test.csv --lib openblas --dgemm -s 64,64 -n 1 -r 1')
        ctx.run('python3 ./multi_runner.py --nb_runs 10 --nb_calls 10 --size 100 -np 1 --csv_file /tmp/test.csv --lib naive --cpu_power=random --scheduler=random --thread_mapping=random --hyperthreading=random')
        ctx.run('python3 ./multi_runner.py --nb_runs 3 --nb_calls 10 --size 100 -np 1 --csv_file /tmp/test.csv --lib naive --likwid CLOCK L3CACHE')

@task
def all(ctx):
    get_openblas_archive(ctx)
    copy_archives(ctx)
    install_apt_packages(ctx)
    install_openblas(ctx)
    install_pip_packages(ctx)
    setup_os(ctx)
    extract_experiment(ctx)
    test_installation(ctx)

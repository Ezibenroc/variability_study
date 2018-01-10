from fabric.api import local, run, cd, env, put
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

def get_openblas_archive():
    if not os.path.isfile(OPENBLAS_ARCHIVE):
        local('wget %s -O %s' % (OPENBLAS_URL, OPENBLAS_ARCHIVE))

def clean():
    run('rm -rf ~/* /usr/lib/openblas-base /usr/lib/libopenblas.so')
    run('yes | pip3 uninstall %s' % ' '.join(PIP_PACKAGES))
    run('yes | apt remove %s' % ' '.join(APT_PACKAGES))

def copy_archives():
    put('openblas.zip', '~')
    put(EXP_ARCHIVE, '~')

def install_apt_packages():
    run('yes | apt upgrade')
    run('yes | apt install %s' % ' '.join(APT_PACKAGES))

def install_openblas():
    run('unzip %s' % OPENBLAS_ARCHIVE)
    with cd(OPENBLAS_DIRECTORY):
        run('make -j 8')
        run('make install PREFIX=/usr')
    run('mkdir /usr/lib/openblas-base/')
    run('ln -s /usr/lib/libopenblas.so /usr/lib/openblas-base/libblas.so')

def install_pip_packages():
    run('wget https://bootstrap.pypa.io/get-pip.py')
    run('python3 get-pip.py')
    run('pip3 install %s' % ' '.join(PIP_PACKAGES))

def setup_os():
    run('modprobe msr')

def extract_experiment():
    run('unzip %s' % EXP_ARCHIVE)

def test_installation():
    with cd(EXP_DIRECTORY):
        run('python3 ./runner.py --csv_file /tmp/test.csv --lib openblas --dgemm -s 64,64 -n 1 -r 1')
        run('python3 ./multi_runner.py --nb_runs 10 --nb_calls 10 --size 100 -np 1 --csv_file /tmp/test.csv --lib naive --cpu_power=random --scheduler=random --thread_mapping=random --hyperthreading=random')
        run('python3 ./multi_runner.py --nb_runs 3 --nb_calls 10 --size 100 -np 1 --csv_file /tmp/test.csv --lib naive --likwid CLOCK L3CACHE')

def all():
    get_openblas_archive()
    copy_archives()
    install_apt_packages()
    install_openblas()
    install_pip_packages()
    setup_os()
    extract_experiment()
    test_installation()

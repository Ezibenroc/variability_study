from fabric.api import local, run, cd, env, put, get, task, runs_once, parallel, execute
from fabric.network import ssh
import os
import zipfile
import shutil

env.use_ssh_config = True
ssh.util.log_to_file('/tmp/paramiko.log', 10)

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

@runs_once
def get_openblas_archive():
    if not os.path.isfile(OPENBLAS_ARCHIVE):
        local('wget %s -O %s' % (OPENBLAS_URL, OPENBLAS_ARCHIVE))

@parallel
def clean():
    run('rm -rf ~/* /usr/lib/openblas-base /usr/lib/libopenblas.so')
    run('yes | pip3 uninstall %s' % ' '.join(PIP_PACKAGES))
    run('yes | apt remove %s' % ' '.join(APT_PACKAGES))

@parallel
def copy_archives():
    put('openblas.zip', '~')
    put(EXP_ARCHIVE, '~')

@parallel
def install_apt_packages():
    run('yes | apt upgrade')
    run('yes | apt install %s' % ' '.join(APT_PACKAGES))

@parallel
def install_openblas():
    run('yes | unzip %s' % OPENBLAS_ARCHIVE)
    with cd(OPENBLAS_DIRECTORY):
        run('make -j 8')
        run('make install PREFIX=/usr')
    run('mkdir /usr/lib/openblas-base/')
    run('ln -s /usr/lib/libopenblas.so /usr/lib/openblas-base/libblas.so')

@parallel
def install_pip_packages():
    run('wget https://bootstrap.pypa.io/get-pip.py')
    run('python3 get-pip.py')
    run('pip3 install %s' % ' '.join(PIP_PACKAGES))

@parallel
def setup_os():
    run('modprobe msr')

@parallel
def extract_experiment():
    run('yes | unzip %s' % EXP_ARCHIVE)

@parallel
def test_installation():
    with cd(EXP_DIRECTORY):
        run('python3 ./runner.py --csv_file /tmp/test.csv --lib openblas --dgemm -s 64,64 -n 1 -r 1')
        run('python3 ./multi_runner.py --nb_runs 10 --nb_calls 10 --size 100 -np 1 --csv_file /tmp/test.csv --lib naive --cpu_power=random --scheduler=random --thread_mapping=random --hyperthreading=random')
        run('python3 ./multi_runner.py --nb_runs 3 --nb_calls 10 --size 100 -np 1 --csv_file /tmp/test.csv --lib naive --likwid CLOCK L3CACHE')

@parallel
def __run_exp(experiment_file):
    result_file = 'tmp.csv'
    with cd(EXP_DIRECTORY):
        put(experiment_file, experiment_file)
        run('python3 %s %s' % (experiment_file, result_file))
        result = get(result_file)
        assert len(result) == 1
        result = result[0]
    return result

@runs_once
def run_exp(experiment_file, result_file):
    results = execute(__run_exp, experiment_file)
    file_names = list(results.values())
    assert len(file_names) > 0
    shutil.copy(file_names[0], result_file)
    for name in file_names[1:]:
        with open(result_file, 'a') as out_f, open(name, 'r') as in_f:
            in_f.readline() # skip the first one, header of the CSV
            for line in in_f:
                out_f.write(line)

@runs_once
def install():
    execute(get_openblas_archive)
    execute(copy_archives)
    execute(install_apt_packages)
    execute(install_openblas)
    execute(install_pip_packages)
    execute(setup_os)
    execute(extract_experiment)
    execute(test_installation)

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

# When running a fab command with --hide stdout,stderr, it seems that fabric
# still gets all the text from the remote machines, it just does not show it.
# This leads to a very high CPU consumption, especially when several hosts are
# used.
# For instance, try running a task that simply calls run('yes').
def run_no_output(cmd):
    run('%s > /dev/null 2>&1' % cmd)

@runs_once
def get_openblas_archive():
    if not os.path.isfile(OPENBLAS_ARCHIVE):
        local('wget %s -O %s' % (OPENBLAS_URL, OPENBLAS_ARCHIVE))

@parallel
def clean():
    run_no_output('rm -rf ~/* /usr/lib/openblas-base /usr/lib/libopenblas.so')
    run_no_output('yes | pip3 uninstall %s' % ' '.join(PIP_PACKAGES))
    run_no_output('yes | apt remove %s' % ' '.join(APT_PACKAGES))

@parallel
def copy_archives():
    put('openblas.zip', '~')
    put(EXP_ARCHIVE, '~')

@parallel
def install_apt_packages():
    run_no_output('yes | apt upgrade')
    run_no_output('yes | apt install %s' % ' '.join(APT_PACKAGES))

@parallel
def install_openblas():
    run_no_output('yes | unzip %s' % OPENBLAS_ARCHIVE)
    with cd(OPENBLAS_DIRECTORY):
        run_no_output('make -j 8')
        run_no_output('make install PREFIX=/usr')
    run_no_output('mkdir /usr/lib/openblas-base/')
    run_no_output('ln -s /usr/lib/libopenblas.so /usr/lib/openblas-base/libblas.so')

@parallel
def install_pip_packages():
    run_no_output('wget https://bootstrap.pypa.io/get-pip.py')
    run_no_output('python3 get-pip.py')
    run_no_output('pip3 install %s' % ' '.join(PIP_PACKAGES))

@parallel
def setup_os():
    run_no_output('modprobe msr')

@parallel
def extract_experiment():
    run_no_output('yes | unzip %s' % EXP_ARCHIVE)

@parallel
def test_installation():
    with cd(EXP_DIRECTORY):
        run_no_output('python3 ./runner.py --csv_file /tmp/test.csv --lib openblas --dgemm -s 64,64 -n 1 -r 1')
        run_no_output('python3 ./multi_runner.py --nb_runs 10 --nb_calls 10 --size 100 -np 1 --csv_file /tmp/test.csv --lib naive --cpu_power=random --scheduler=random --thread_mapping=random --hyperthreading=random')
        run_no_output('python3 ./multi_runner.py --nb_runs 3 --nb_calls 10 --size 100 -np 1 --csv_file /tmp/test.csv --lib naive --likwid CLOCK L3CACHE')

@parallel
def __run_exp(experiment_file):
    result_file = 'tmp.csv'
    with cd(EXP_DIRECTORY):
        put(experiment_file, experiment_file)
        run_no_output('python3 %s %s' % (experiment_file, result_file))
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

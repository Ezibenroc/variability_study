#! /usr/bin/env bash

function run_command {
    if [ $# -ne 2 ]; then
        echo "Wrong args: $*"
    fi
    hostname=$1
    command=$2
    logfile="run_${hostname}.log"
    echo "###[$(date '+%Y-%m-%d %H:%M:%S')] ${command}" >> ${logfile}
	ssh root@${hostname} "${command}" &>> ${logfile}
    if [ $? -ne 0 ]; then
        echo "Error on host ${hostname} with command ${command}"
        exit 1
    fi
}

[ -f openblas.zip ] || wget https://github.com/xianyi/OpenBLAS/archive/v0.2.20.zip -O openblas.zip
rm run_*.log
for host in $*; do {	
    run_command ${host} 'rm -rf variability_study.zip variability_study scripts.zip scripts openblas.zip OpenBLAS* /usr/lib/openblas-base'
    scp -q openblas.zip root@${host}:/root
    scp -q variability_study.zip  root@${host}:/root
    run_command ${host} 'yes | apt upgrade'
    run_command ${host} 'yes | apt install build-essential python python3 python3-dev zip linux-cpupower make linux-tools git numactl likwid time cpufrequtils hwloc'
    run_command ${host} 'unzip openblas.zip'
    run_command ${host} 'cd OpenBLAS* && make -j 8 && make install PREFIX=/usr && mkdir /usr/lib/openblas-base/ && ln -s /usr/lib/libopenblas.so /usr/lib/openblas-base/libblas.so'
    run_command ${host} 'unzip variability_study.zip'
    run_command ${host} 'wget https://bootstrap.pypa.io/get-pip.py && python3 get-pip.py && pip3 install psutil py-cpuinfo GitPython pandas lxml'
    run_command ${host} 'cd variability_study/intercoolr && make'
    run_command ${host} 'cd variability_study && python3 ./runner.py --csv_file /tmp/test.csv --lib openblas --dgemm -s 64,64 -n 1 -r 1 --stat'
    run_command ${host} 'cd variability_study && python3 ./multi_runner.py --nb_runs 10 --nb_calls 10 --size 100 -np 1 --csv_file /tmp/test.csv --lib naive --cpu_power=random --scheduler=random --thread_mapping=random --hyperthreading=random'
    run_command ${host} 'modprobe msr'
    run_command ${host} 'cd variability_study && python3 ./multi_runner.py --nb_runs 3 --nb_calls 10 --size 100 -np 1 --csv_file /tmp/test.csv --lib naive --likwid CLOCK L3CACHE'
    run_command ${host} 'likwid-perfctr -a'
    echo "DONE for ${host}"
}&
done
wait

echo "Terminated."

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
    run_command ${host} 'rm -rf scripts.zip scripts openblas.zip OpenBLAS* /usr/lib/openblas-base'
    run_command ${host} 'cp /home/tocornebize/openblas.zip .'
    run_command ${host} 'unzip openblas.zip'
    run_command ${host} 'cd OpenBLAS* && make -j 8 && make install PREFIX=/usr && mkdir /usr/lib/openblas-base/ && ln -s /usr/lib/libopenblas.so /usr/lib/openblas-base/libblas.so'
    run_command ${host} 'cp /home/tocornebize/scripts.zip .'
    run_command ${host} 'unzip scripts.zip'
    run_command ${host} 'cd scripts/cblas_tests && python3 ./runner.py --csv_file /tmp/test.csv --lib openblas --dgemm -s 64,64 -n 1 -r 1'
    echo "DONE for ${host}"
}&
done
wait

echo "Terminated."

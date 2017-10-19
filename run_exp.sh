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

rm *.csv
rm run_*.log

for host in $*; do {	
    run_command ${host} 'cd scripts/cblas_tests && python3 ./runner.py --csv_file /tmp/results_`hostname`.csv --lib openblas --dgemm -s 1024,1024 -n 50 -r 1 -np $(nproc --all) --stat'
    scp root@${host}:/tmp/results\*.csv .
}&
done
wait

head -n 1 results_${1}.*.csv > results.csv
for host in $*; do
    tail -n +2 results_${host}.*.csv >> results.csv
done

echo "Terminated."

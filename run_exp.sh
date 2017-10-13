#! /usr/bin/env zsh

function run_command {
    if [ $# -ne 2 ]; then
        echo "Wrong args: $*"
    fi
    hostname=$1
    command=$2
    logfile="run_${hostname}.log"
    echo "### ${command}" >> ${logfile}
	ssh root@${hostname} "${command}" &>> ${logfile}
    if [ $? -ne 0 ]; then
        echo "Error on host ${hostname} with command ${command}"
        exit 1
    fi
}

rm *.csv

for host in $*; do {	
    rm -f "run_*.log"
    run_command ${host} 'yes | apt install libopenblas-base libopenblas-dev'
    run_command ${host} 'rm -rf scripts.zip scripts'
    run_command ${host} 'cp /home/tocornebize/scripts.zip .'
    run_command ${host} 'unzip scripts.zip'
    run_command ${host} 'cd scripts/cblas_tests && python3 ./runner.py --csv_file /tmp/results_`hostname`.csv --lib openblas --dgemm -s 1024,1024 -n 50 -r 1'
    scp ${host}:/tmp/results\*.csv .
    echo "DONE for ${host}"
}&
done
wait

head -n 1 results_${1}.*.csv > results.csv
for host in $*; do
    tail -n +2 results_${host}.*.csv >> results.csv
done

echo "Terminated."

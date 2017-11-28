#include <stdlib.h>
#include <stdio.h>
#include <time.h>
#include <sys/time.h>
#include <assert.h>
#include <string.h>
#include <likwid.h>
#include <omp.h>
#include <sched.h>
#include "common_matrix.h"

void syntax(char *exec_name) {
    fprintf(stderr, "Syntax: %s <nb_calls> <size> [output_file]\n", exec_name);
    exit(1);
}

int main(int argc, char* argv[]) {
    if (argc != 3 && argc != 4)
        syntax(argv[0]);

    int nb_calls = atoi(argv[1]);
    int size    = atoi(argv[2]);
    FILE *outfile;
    if(argc == 3)
        outfile = stdout;
    else
        outfile = fopen(argv[3], "w");
    if(size <= 0 || nb_calls <= 0)
        syntax(argv[0]);
    double *A = allocate_matrix(size);
    double *B = allocate_matrix(size);
    double *C = allocate_matrix(size);

    double alpha = 1.;
    double beta = 1.;

#ifdef LIKWID_PERFMON
    char *likwid_filename = getenv("LIKWID_FILENAME");
    FILE *likwid_outfile;
    if(likwid_filename == NULL)
        likwid_outfile = stdout;
    else
        likwid_outfile = fopen(likwid_filename, "w");
    LIKWID_MARKER_INIT;
    #pragma omp parallel
    {
        LIKWID_MARKER_THREADINIT;
        LIKWID_MARKER_REGISTER("perf_dgemm");
    }
    assert(perfmon_getNumberOfGroups() == 1); // we do not handle the multi-group case (yet?)
#endif
    struct timeval before = {};
    struct timeval after = {};

    for(int i = 0; i < nb_calls; i++) {
#ifdef LIKWID_PERFMON
        #pragma omp parallel
        {
            LIKWID_MARKER_START("perf_dgemm");
        }
#endif
        gettimeofday(&before, NULL);
        matrix_product(A, B, C, size);
#ifdef LIKWID_PERFMON
// See https://github.com/RRZE-HPC/likwid/issues/131 for the discussion about cumulative values.
        #pragma omp parallel
        {
            LIKWID_MARKER_STOP("perf_dgemm");
            int nevents = 0; // No need to fill the events array, so nevents is set to 0
            double time;
            int count;
            LIKWID_MARKER_GET("perf_dgemm", &nevents, NULL, &time, &count);
            int my_thread_id = omp_get_thread_num();
            for(int nthread = 0; nthread < omp_get_num_threads(); nthread++) {
                if(my_thread_id == nthread) {
                    fprintf(likwid_outfile, "%d,%f,%d,%d", i, time, my_thread_id,
                        likwid_getProcessorId());
                    for (int ev = 0; ev < perfmon_getNumberOfEvents(0); ev++) {
                        fprintf(likwid_outfile, ",%f", perfmon_getLastResult(0, ev, nthread));
                    }
                    fprintf(likwid_outfile, "\n");
                }
                #pragma omp barrier
            }
        }
#endif
        gettimeofday(&after, NULL);
        double total_time = (after.tv_sec-before.tv_sec) + 1e-6*(after.tv_usec-before.tv_usec);
        fprintf(outfile, "%f\n", total_time);
    }

    if(outfile != stdout)
        fclose(outfile);
    free_matrix(A);
    free_matrix(B);
    free_matrix(C);
#ifdef LIKWID_PERFMON
    LIKWID_MARKER_CLOSE;
    if(likwid_outfile != stdout)
        fclose(likwid_outfile);
#endif
    return 0;
}

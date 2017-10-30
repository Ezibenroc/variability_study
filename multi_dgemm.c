#include <stdlib.h>
#include <stdio.h>
#include <time.h>
#include <sys/time.h>
#include <assert.h>
#include <string.h>
#include "common_matrix.h"

void syntax(char *exec_name) {
    fprintf(stderr, "Syntax: %s <nb_calls> <size>\n", exec_name);
    exit(1);
}

int main(int argc, char* argv[])
{
    if (argc != 3)
        syntax(argv[0]);

    int nb_calls = atoi(argv[1]);
    int size    = atoi(argv[2]);
    if(size <= 0 || nb_calls <= 0)
        syntax(argv[0]);
    double *A = allocate_matrix(size);
    double *B = allocate_matrix(size);
    double *C = allocate_matrix(size);

    double alpha = 1.;
    double beta = 1.;

    struct timeval before = {};
    struct timeval after = {};

    int i;
    for(i = 0; i < nb_calls; i++) {
        gettimeofday(&before, NULL);
	matrix_product(A, B, C, size);
        gettimeofday(&after, NULL);
        double total_time = (after.tv_sec-before.tv_sec) + 1e-6*(after.tv_usec-before.tv_usec);
        printf("%f\n", total_time);
    }

    free_matrix(A);
    free_matrix(B);
    free_matrix(C);
    return 0;
}

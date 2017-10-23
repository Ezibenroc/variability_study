#include <stdlib.h>
#include <stdio.h>
#include <time.h>
#include <sys/time.h>
#include <assert.h>
#include <string.h>
#ifdef USE_MKL
#include <mkl.h>
#else
#include <cblas.h>
#endif

void syntax(char *exec_name) {
    fprintf(stderr, "Syntax: %s <nb_calls> <size>\n", exec_name);
    exit(1);
}

double *allocate_matrix(int size) {
    double *result = (double*) malloc(size*size*sizeof(double));
    memset(result, 1, size*size*sizeof(double));
    assert(result);
    return result;
}

void free_matrix(double *matrix) {
    free(matrix);
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

    for(int i = 0; i < nb_calls; i++) {
        gettimeofday(&before, NULL);
        cblas_dgemm(CblasColMajor, CblasNoTrans, CblasTrans, size, size, size, alpha, A, size, B, size, beta, C, size);
        gettimeofday(&after, NULL);
        double total_time = (after.tv_sec-before.tv_sec) + 1e-6*(after.tv_usec-before.tv_usec);
        printf("%f\n", total_time);
    }

    free_matrix(A);
    free_matrix(B);
    free_matrix(C);
    return 0;
}

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

// Warning: we use dgemm in Column-major mode, to be like HPL.
// It is different than the implementation of 2D arrays in C (which are row-major).

// We transpose the second matrix, as in HPL.

// One should keep in mind these two things when calling dgemm.
// When we say that a matrix has a size x*y, we may mean its transpose.

void syntax(char *exec_name) {
    fprintf(stderr, "Syntax: %s <m> <n> <k> <lead_A> <lead_B> <lead_C>\n", exec_name);
    fprintf(stderr, "Perform the operation C = A×B, where:\n");
    fprintf(stderr, "\tA is a matrix of size m×k and has a leading dimension of lead_A\n");
    fprintf(stderr, "\tB is a matrix of size k×n and has a leading dimension of lead_B\n");
    fprintf(stderr, "\tC is a matrix of size m×n and has a leading dimension of lead_C\n");
    exit(1);
}

double *allocate_matrix(int x, int y, int lead_dim) {
    assert(lead_dim >= x);
    double *result = (double*) malloc(lead_dim*y*sizeof(double));
    memset(result, 1, lead_dim*y*sizeof(double));
    assert(result);
    return result;
}

void free_matrix(double *matrix) {
    free(matrix);
}

int main(int argc, char* argv[])
{
	if (argc != 7)
        syntax(argv[0]);

	int m, n, k, lead_A, lead_B, lead_C;
    
    m      = atoi(argv[1]);
    n      = atoi(argv[2]);
    k      = atoi(argv[3]);
    lead_A = atoi(argv[4]);
    lead_B = atoi(argv[5]);
    lead_C = atoi(argv[6]);
    if(m <= 0 || n <= 0 || k <= 0 ||
            lead_A <= 0 || lead_B <= 0 || lead_C <= 0)
        syntax(argv[0]);
    double *A = allocate_matrix(m, k, lead_A);
    double *B = allocate_matrix(n, k, lead_B); // k and n are swapped here, since the matrix is transposed in dgemm
    double *C = allocate_matrix(m, n, lead_C);

	double alpha = 1.;
	double beta = 1.;

    struct timeval before = {};
    struct timeval after = {};

    // Warmup
    cblas_dgemm(CblasColMajor, CblasNoTrans, CblasTrans, m, n, k, alpha, A, lead_A, B, lead_B, beta, C, lead_C);

    gettimeofday(&before, NULL);
    cblas_dgemm(CblasColMajor, CblasNoTrans, CblasTrans, m, n, k, alpha, A, lead_A, B, lead_B, beta, C, lead_C);
    gettimeofday(&after, NULL);

    double total_time = (after.tv_sec-before.tv_sec) + 1e-6*(after.tv_usec-before.tv_usec);

    printf("%f\n", total_time);

    free_matrix(A);
    free_matrix(B);
    free_matrix(C);
    return 0;
}

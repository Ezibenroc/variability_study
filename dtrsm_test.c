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
    fprintf(stderr, "Syntax: %s <m> <n> <lead_A> <lead_B>\n", exec_name);
    fprintf(stderr, "Solve the system A*X=alpha*B, where:\n");
    fprintf(stderr, "\tA is a matrix of size m×n and has a leading dimension of lead_A\n");
    fprintf(stderr, "\tB is a matrix of size m×n and has a leading dimension of lead_B\n");
    fprintf(stderr, "\tX is a matrix of size m×n and has a leading dimension of lead_B\n");
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
	if (argc != 5)
        syntax(argv[0]);

	int m, n, lead_A, lead_B;
    
    m      = atoi(argv[1]);
    n      = atoi(argv[2]);
    lead_A = atoi(argv[3]);
    lead_B = atoi(argv[4]);
    if(m <= 0 || n <= 0 ||
            lead_A <= 0 || lead_B <= 0)
        syntax(argv[0]);
    double *A = allocate_matrix(m, n, lead_A);
    double *B = allocate_matrix(m, n, lead_B);

	double alpha = 1.;

    struct timeval before = {};
    struct timeval after = {};

    // Warmup
    cblas_dtrsm(CblasColMajor, CblasRight, CblasLower, CblasNoTrans, CblasUnit, m, n, alpha, A, lead_A, B, lead_B);

    gettimeofday(&before, NULL);
    cblas_dtrsm(CblasColMajor, CblasRight, CblasLower, CblasNoTrans, CblasUnit, m, n, alpha, A, lead_A, B, lead_B);
    gettimeofday(&after, NULL);

    double total_time = (after.tv_sec-before.tv_sec) + 1e-6*(after.tv_usec-before.tv_usec);

    printf("%f\n", total_time);

    free_matrix(A);
    free_matrix(B);
    return 0;
}

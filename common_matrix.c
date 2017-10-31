#include "common_matrix.h"

#ifdef USE_MKL
#pragma message "Using the MKL for BLAS."
#include <mkl.h>
#endif
#ifdef USE_NAIVE
#pragma message "Using a custom implementaiton for BLAS."
#include <omp.h>
#endif
#ifdef USE_OPENBLAS
#pragma message "Using OpenBLAS for BLAS."
#include <cblas.h>
#endif
#ifdef USE_ATLAS
#pragma message "Using Atlas for BLAS."
#include <cblas.h>
#endif

void matrix_product(double *A, double *B, double *C, int size) {
#ifdef USE_NAIVE
    #pragma omp parallel
    {
    for(int k = 0 ; k < size ; k++) {
        #pragma omp for // collapse(2) // ← doing the j-loop in parallel slow down the execution by a factor 2 (hypothesis: more cache miss)
        for(int i = 0 ; i < size ; i++) {
            for(int j = 0 ; j < size ; j++) {
                double a = matrix_get(A, size, i, k);
                double b = matrix_get(B, size, k, j);
                double c = matrix_get(C, size, i, j);
                matrix_set(C, size, i, j, c + a*b);
            }
        }
    }
    }
#else
    double alpha = 1.;
    double beta = 1.;
    cblas_dgemm(CblasRowMajor, CblasNoTrans, CblasNoTrans, size, size, size, alpha, A, size, B, size, beta, C, size);
#endif
}

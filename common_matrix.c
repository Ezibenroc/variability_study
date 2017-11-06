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

#define BLOCK_SIZE 128

inline int min(int a, int b) {
    return a < b ? a : b;
}

void matrix_product(double *A, double *B, double *C, int size) {
#ifdef USE_NAIVE
    #pragma omp parallel
    {
    for(int i0 = 0 ; i0 < size ; i0 += BLOCK_SIZE) {
        #pragma omp for // collapse(2) // ← doing the j-loop in parallel slow down the execution by a factor 2 (hypothesis: more cache miss)
        for(int j0 = 0 ; j0 < size ; j0 += BLOCK_SIZE) {
            for(int k0 = 0 ; k0 < size ; k0 += BLOCK_SIZE) {
                for(int k = k0 ; k < min(k0+BLOCK_SIZE, size) ; k++) {
                    for(int i = i0 ; i < min(i0+BLOCK_SIZE, size) ; i++) {
                        for(int j = j0 ; j < min(j0+BLOCK_SIZE, size) ; j++) {
                            double a = matrix_get(A, size, i, k);
                            double b = matrix_get(B, size, k, j);
                            double c = matrix_get(C, size, i, j);
                            matrix_set(C, size, i, j, c + a*b);
                        }
                    }
                }
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

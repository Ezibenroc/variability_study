#ifndef COMMON_MATRIX_H
#define COMMON_MATRIX_H
#include <assert.h>
#include <string.h>

inline double *allocate_matrix(int size) {
    double *result = (double*) malloc(size*size*sizeof(double));
    memset(result, 1, size*size*sizeof(double));
    assert(result);
    return result;
}

inline void free_matrix(double *matrix) {
    free(matrix);
}

void matrix_product(double *A, double *B, double *C, int size);

#endif

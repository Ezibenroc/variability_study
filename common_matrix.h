#ifndef COMMON_MATRIX_H
#define COMMON_MATRIX_H
#include <assert.h>
#include <string.h>
#include <stdlib.h>

inline double *allocate_matrix(int size) {
    double *result = (double*) malloc(size*size*sizeof(double));
    memset(result, 1, size*size*sizeof(double));
    assert(result);
    return result;
}

inline void free_matrix(double *matrix) {
    free(matrix);
}

inline void matrix_set(double *matrix, int size, int i, int j, double value) {
    matrix[i*size+j] = value;
}

inline double matrix_get(double *matrix, int size, int i, int j) {
    return matrix[i*size+j];
}

void matrix_product(double *A, double *B, double *C, int size);

#endif

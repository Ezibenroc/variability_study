#include <stdio.h>
#include "common_matrix.h"

// Example of compilation:
// gcc ./test_matmul.c  ./common_matrix.c -DUSE_NAIVE -O3 -o ./test_matmul

// A[i][j] = i
double *init_matrix_A(int size) {
    double *matrix = allocate_matrix(size);
    for(int i = 0 ; i < size ; i++) {
        for(int j = 0 ; j < size ; j++) {
            matrix_set(matrix, size, i, j, i);
        }
    }
    return matrix;
}

// B[i][j] = i+j
double *init_matrix_B(int size) {
    double *matrix = allocate_matrix(size);
    for(int i = 0 ; i < size ; i++) {
        for(int j = 0 ; j < size ; j++) {
            matrix_set(matrix, size, i, j, i+j);
        }
    }
    return matrix;
}

// C[i][j] = 0
double *init_matrix_C(int size) {
    double *matrix = allocate_matrix(size);
    memset(matrix, 0, size*size*sizeof(double *));
    return matrix;
}

double matrix_sum(double *matrix, int size) {
    double sum = 0;
    for(int i = 0 ; i < size ; i++) {
        for(int j = 0 ; j < size ; j++) {
            sum += matrix_get(matrix, size, i, j);
        }
    }
    return sum;
}

inline double my_abs(double x) {
    return x > 0 ? x : -x ;
}

int main() {
    for(int matrix_size = 100 ; matrix_size <= 1500 ; matrix_size += 100) {
        printf("Testing size=%d...\n", matrix_size);
        double *matrix_A = init_matrix_A(matrix_size);
        double *matrix_B = init_matrix_B(matrix_size);
        double *matrix_C = init_matrix_C(matrix_size);
        matrix_product(matrix_A, matrix_B, matrix_C, matrix_size);
        double sum = matrix_sum(matrix_C, matrix_size);
        double N = matrix_size;
        double expected = N*N*N*(N-1)*(N-1)/2;
        free_matrix(matrix_A);
        free_matrix(matrix_B);
        free_matrix(matrix_C);
        if(my_abs((sum-expected)/expected) > 1e-6) {
            printf("Error with the matrix sum (size = %d).\n", matrix_size);
            printf("Expected: %f\n", expected);
            printf("Observed: %f\n", sum);
            exit(1);
        }
    }
    printf("OK\n");
    return 0;
}

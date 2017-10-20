#define _POSIX_C_SOURCE 199309L // to make time function work, wtf... see here: http://stackoverflow.com/questions/26769129/trying-to-use-clock-gettime-but-getting-plenty-of-undeclared-errors-from-ti

#include <stdio.h>
#include <stdlib.h>
#include <sys/time.h>
#include <assert.h>
#include <string.h>
#include <omp.h>

float *allocate_matrix(int size) {
    float *matrix = (float*) malloc(sizeof(float*)*size*size);
    assert(matrix);
    return matrix;
}

void free_matrix(float *matrix) {
    free(matrix);
}

inline void matrix_set(float *matrix, int size, int i, int j, float value) {
    matrix[i*size+j] = value;
}

inline float matrix_get(float *matrix, int size, int i, int j) {
    return matrix[i*size+j];
}

void matrix_product(float *A, float *B, float *C, int size) {
    for(int k = 0 ; k < size ; k++) {
        #pragma omp for // collapse(2) // ← doing the j-loop in parallel slow down the execution by a factor 2 (hypothesis: more cache miss)
        for(int i = 0 ; i < size ; i++) {
            for(int j = 0 ; j < size ; j++) {
                float a = matrix_get(A, size, i, k);
                float b = matrix_get(B, size, k, j);
                float c = matrix_get(C, size, i, j);
                matrix_set(C, size, i, j, c + a*b);
            }
        }
    }
}

int main(int argc, char *argv[]) {
    omp_set_nested(1);

    int matrix_size = 0;

    if (argc != 2) {
	fprintf(stderr, "Syntax: %s <matrix_size>\n", argv[0]);
	exit(1);
    }
    else {
        matrix_size = atoi(argv[1]);
    }

    float *matrix_A = allocate_matrix(matrix_size);
    float *matrix_B = allocate_matrix(matrix_size);
    float *matrix_C = allocate_matrix(matrix_size);

    struct timeval before = {};
    struct timeval after = {};

    gettimeofday(&before, NULL);
    #pragma omp parallel
    {
        matrix_product(matrix_A, matrix_B, matrix_C, matrix_size);
    }
    gettimeofday(&after, NULL);


    double total_time = (after.tv_sec-before.tv_sec) + 1e-6*(after.tv_usec-before.tv_usec);

    printf("%f\n", total_time);

    free_matrix(matrix_A);
    free_matrix(matrix_B);
    free_matrix(matrix_C);
    return 0;
}

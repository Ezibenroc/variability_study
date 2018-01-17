from experiment import *
import sys

app = Dgemm(lib='openblas',
            size=512,
            nb_calls=5,
            nb_threads=1,
            block_size=64, # ignored for OpenBLAS
)

wrappers= [
    CommandLine(),
    Date(),
    Platform(),
    CPU(),
    Time()
]

if __name__ == '__main__':
    if len(sys.argv) != 2:
        sys.exit('Syntax: %s <result_file>' % sys.argv[0])
    ExpEngine(application=app, wrappers=wrappers).run_all(
        nb_runs=5,
        filename=sys.argv[1],
    )

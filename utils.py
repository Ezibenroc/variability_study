from subprocess import Popen, PIPE
try:
    from subprocess import DEVNULL
except ImportError:
    DEVNULL = open('/dev/null', 'w')
import logging
import warnings # psutil gives some warnings, let's just ignore them
warnings.simplefilter("ignore")

logger = logging.getLogger(__name__)
logger.setLevel(level=logging.DEBUG)
fh = logging.StreamHandler()
fh.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
logger.addHandler(fh)

def error(msg, stdout=None, stderr=None):
    logger.error(msg)
    if stdout:
        logger.error(stdout)
    if stderr:
        logger.error(stderr)
    sys.exit(1)

def run_command(args):
    logger.info(' '.join(args))
    process = Popen(args, stdout=PIPE, stderr=PIPE)
    output = process.communicate()
    if process.wait() != 0:
        error('with command: %s' % ' '.join(args), output[0].decode('utf8'), output[1].decode('utf8'))
    return output[0]

class LibraryNotFound(Exception):
    pass

def compile_generic(exec_filename, lib, block_size=128, likwid=None):
    c_filename = exec_filename + '.c'
    options = []
    if likwid is not None:
        options.extend(['-DLIKWID_PERFMON', '-llikwid'])
    lib_to_command = {
        'mkl': ['icc', '-DUSE_MKL', c_filename, '-std=gnu99', 'common_matrix.c', '-fopenmp', '-mkl', '-O3', '-o', exec_filename, *options],
        'mkl2': ['/opt/intel/bin/icc', '-DUSE_MKL', '-std=gnu99', c_filename, 'common_matrix.c', '-I', '/opt/intel/compilers_and_libraries_2017.0.098/linux/mkl/include',
		'/opt/intel/mkl/lib/intel64/libmkl_rt.so', '-O3', '-o', exec_filename, *options], # an ugly command for a non-standard library location
        'atlas': ['gcc', '-DUSE_ATLAS', c_filename, '-std=gnu99', 'common_matrix.c', '-fopenmp', '/usr/lib/atlas-base/libcblas.so.3', '-O3', '-o', exec_filename, *options],
        'openblas': ['gcc', '-DUSE_OPENBLAS', c_filename, '-std=gnu99', 'common_matrix.c', '-fopenmp', '/usr/lib/openblas-base/libblas.so', '-O3', '-o', exec_filename, *options],
        'naive': ['gcc', '-DBLOCK_SIZE=%d' % block_size, *options, '-std=gnu99', '-fopenmp', '-DUSE_NAIVE', c_filename, 'common_matrix.c', '-O3', '-o', exec_filename, *options],
    }
    try:
        run_command(lib_to_command[lib])
    except KeyError:
        raise LibraryNotFound('Library unknown. The possible choices are %s' % list(lib_to_command.keys()))

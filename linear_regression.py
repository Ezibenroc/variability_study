#!/usr/bin/env python3

import sys
from pandas import DataFrame
import statsmodels.formula.api as statsmodels

def get_reg(filename):
    if 'dgemm' in filename:
        model = 'time ~ I(m*n*k)'
    elif 'dtrsm' in filename:
        model = 'time ~ I(m*n**2)'
    else:
        sys.stderr.write('ERROR, did not recognize experiment with file name.\n')
        sys.exit(1)
    dataframe = DataFrame.from_csv(filename, index_col=None)
    reg = statsmodels.ols(formula=model, data=dataframe).fit()
    if reg.rsquared < 0.95:
        print('WARNING: bad R-squared, got %f.' % reg.rsquared)
    return reg

if __name__ == '__main__':
    if len(sys.argv) != 2:
        print('Syntax: %s <file_name>' % sys.argv[0])
        sys.exit(1)
    reg = get_reg(sys.argv[1])
    print(reg.params)

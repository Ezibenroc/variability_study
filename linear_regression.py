#!/usr/bin/env python3

import sys
from pandas import DataFrame
import statsmodels.formula.api as statsmodels

def get_reg(filename):
    dataframe = DataFrame.from_csv(filename, index_col=None)
    model = 'time ~ size_product'
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

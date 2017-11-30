#! /usr/bin/env python3

import sys
from pandas import DataFrame

def read_csv(filename):
    df = DataFrame.from_csv(filename, index_col=None)
    df['index'] = range(1, len(df)+1)
    df['filename'] = filename
    return df


def compute_subset(df, row, variables):
    subset = df
    for var in variables:
        subset = subset[subset[var] == row[var]]
    return subset

def compare_row(control_rows, row, control_variables, excluded_variables, delta=0.1):
    error = 0
    for var in control_rows.keys():
        if var in control_variables or var in excluded_variables:
            continue
        minval = control_rows[var].min()
        maxval = control_rows[var].max()
        real_value = row[var]
        try:
            min_expected = minval * (1-delta)
            max_expected = maxval * (1+delta)
            if min_expected > real_value or max_expected < real_value:
                sys.stderr.write('ERROR for key "%s"\n' % var)
                sys.stderr.write('Expected a value in [%g, %g] (file %s), got %g (file %s, line %d)\n\n' % (min_expected, max_expected, control_rows['filename'].unique()[0], real_value, row['filename'], row['index']))
                error += 1
        except TypeError: # non-numeric type
            if minval != maxval:
                raise ValueError('Do not know what to compare, got different candidate values in the control dataset for field %s: %s and %s.' % (var, minval, maxval))
            if minval != real_value:
                sys.stderr.write('ERROR for key "%s"\n' % var)
                sys.stderr.write('Expected a value equal to %s (file %s), got %s (file %s, line %d)\n\n' % (minval, control_rows['filename'].unique()[0], real_value, row['filename'], row['index']))
                error += 1
    return error

def compare(df, row, control_variables, excluded_variables):
    subset = compute_subset(df, row, control_variables)
    return compare_row(subset, row, control_variables, excluded_variables)

def compare_all(df1, df2, control_variables, excluded_variables):
    error = 0
    for row in df2.iterrows():
        error += compare(df1, row[1], control_variables, excluded_variables)
    return error

if __name__ == '__main__':
    if len(sys.argv) != 5:
        sys.stderr.write('Syntax: %s <CSV file> <CSV file> <control variables> <excluded_variables>\n' % sys.argv[0])
        sys.stderr.write('Example: %s control_file.csv new_file.csv size,nb_threads date,hour,git_hash\n' % sys.argv[0])
        sys.stderr.write('         It will check if the rows from the two files which share a common size and nb_threads are equal (excluding fields date, hour and git_hash).\n')
        sys.exit(1)
    df1 = read_csv(sys.argv[1])
    df2 = read_csv(sys.argv[2])
    control_variables = sys.argv[3].split(',')
    excluded_variables = sys.argv[4].split(',')
    error = compare_all(df1, df2, control_variables, excluded_variables)
    if error > 0:
        sys.stderr.write('Total number of errors: %d\n' % error)
        sys.exit(1)

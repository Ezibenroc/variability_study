#! /usr/bin/env python3
import fileinput

def mean(l):
    return sum(l)/len(l)

def variability(l):
    return (max(l)-min(l))/mean(l)

if __name__ == '__main__':
    times = [float(x) for x in fileinput.input()]
    print(variability(times))

#!/usr/bin/env sh
# Convenience script for compiling with cython on my system, for speed.

cython cryptowatcher.py --embed
gcc -march=x86-64 -mtune=haswell -O2 -I /usr/include/python3.6m -o cryptowatcher cryptowatcher.c -lpython3.6m -lpthread -lm -lutil -ldl

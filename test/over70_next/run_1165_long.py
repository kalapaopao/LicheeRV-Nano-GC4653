#!/usr/bin/env python3
"""72s test at HTS1165 VTS1200 with 6 spaced original NV21 samples and 4s MIPI/thermal checks."""
import run_lab as lab
lab.STEPS=(1165,)
lab.DURATION_SECONDS=72
lab.SAMPLE_LIMIT=6
lab.SAMPLE_INTERVAL=10
lab.STOP_ON_TARGET=False
if __name__=='__main__':lab.main()

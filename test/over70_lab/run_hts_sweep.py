#!/usr/bin/env python3
"""Conservative downward HTS sweep; stops at first invalid frame/MIPI/raw result."""
import run_lab as lab
lab.STEPS=(1175,1170,1165,1160,1150)
lab.DURATION_SECONDS=16
lab.SAMPLE_LIMIT=3
lab.SAMPLE_INTERVAL=4
lab.STOP_ON_TARGET=False
if __name__=="__main__":lab.main()

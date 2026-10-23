#!/usr/bin/env python3
"""27 MHz read-only baseline for the 36MHz-capable user application.
Does not load/replace any kernel modules or use 36MHz on the shipping driver.
"""
import run_spec27_hts as baseline
baseline.BINARY=baseline.ROOT/"minraw36"/"minraw36"
baseline.STEPS=(1600,)
baseline.DURATION_SECONDS=8
if __name__=="__main__":baseline.main()

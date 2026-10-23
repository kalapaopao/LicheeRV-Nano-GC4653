#!/usr/bin/env python3
"""Short HTS1165/VTS1200 isolated boundary check; auto-stop on error."""
import run_lab as lab
lab.STEPS=(1165,)
lab.DURATION_SECONDS=16
lab.SAMPLE_LIMIT=3
lab.SAMPLE_INTERVAL=4
lab.STOP_ON_TARGET=False
if __name__=='__main__':lab.main()

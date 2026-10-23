#!/usr/bin/env python3
"""72s HTS1175 VTS1200, samples6, MIPI polls every4s; no other parameter change."""
import run_lab as lab
lab.STEPS=(1175,)
lab.DURATION_SECONDS=72
lab.SAMPLE_LIMIT=6
lab.SAMPLE_INTERVAL=10
lab.STOP_ON_TARGET=False
if __name__=='__main__':lab.main()

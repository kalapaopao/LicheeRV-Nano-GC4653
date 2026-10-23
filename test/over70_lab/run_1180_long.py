#!/usr/bin/env python3
"""112s test at HTS1180 with six samples 15 seconds apart and MIPI/thermal monitoring every 4s."""
import run_lab as lab
lab.STEPS=(1180,)
lab.DURATION_SECONDS=112
lab.SAMPLE_LIMIT=6
lab.SAMPLE_INTERVAL=15
if __name__=="__main__":lab.main()

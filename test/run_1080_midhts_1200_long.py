#!/usr/bin/env python3
"""45-second endurance check of HTS1200, unchanged 27MHz MCLK, Factory 1080P."""
import run_1080_midhts as exp
exp.STEPS=(1200,)
exp.DURATION_SECONDS=45
if __name__=="__main__":exp.main()

#!/usr/bin/env python3
"""40-second validation of the conservative within-spec 27MHz/HTS=1575 mode."""
import run_spec27_hts as experiment
experiment.STEPS=(1575,)
experiment.DURATION_SECONDS=40
if __name__=="__main__":
    experiment.main()

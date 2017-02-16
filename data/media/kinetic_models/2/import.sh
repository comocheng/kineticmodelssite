#!/bin/bash
#BSUB -J port8156
#BSUB -oo output.log
#BSUB -eo error.log
#BSUB -n 1

python -m cProfile -o importChemkin.profile $RMGpy/importChemkin.py  \
	--species data/media/kinetic_models/2/chemkin.txt \
	--reactions data/media/kinetic_models/2/chemkin.txt \
	--thermo data/media/kinetic_models/2/thermo.txt \
	--known data/media/kinetic_models/2/SMILES.txt \
	--port 8156
gprof2dot -f pstats  importChemkin.profile | dot -Tpdf -o importChemkin.profile.pdf
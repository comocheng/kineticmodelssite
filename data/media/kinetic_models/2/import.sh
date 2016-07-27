#!/bin/bash
#BSUB -J port8156
#BSUB -oo output.log
#BSUB -eo error.log
#BSUB -n 1

python -m cProfile -o importChemkin.profile $RMGpy/importChemkin.py  \
	--species chemkin.txt \
	--reactions chemkin.txt \
	--thermo thermo.txt \
	--known SMILES.txt \
	--port 8156
gprof2dot -f pstats  importChemkin.profile | dot -Tpdf -o importChemkin.profile.pdf
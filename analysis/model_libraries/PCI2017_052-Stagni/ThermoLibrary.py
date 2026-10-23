#!/usr/bin/env python
# encoding: utf-8

name = "PCI2017/052-Stagni"
shortDesc = "Thermo library for species appearing in shared reactions with Harris-Butane"
longDesc = """
Thermo entries from model PCI2017/052-Stagni
filtered to species that participate in reactions shared with Harris-Butane.
Auto-generated from the kinetic-models database.
"""
entry(
    index = 0,
    label = "C2H2O",
    molecule = 
"""
1 O u0 p2 c0 {3,D}
2 C u0 p0 c0 {3,D} {4,S} {5,S}
3 C u0 p0 c0 {1,D} {2,D}
4 H u0 p0 c0 {2,S}
5 H u0 p0 c0 {2,S}
""",
    thermo = NASA(
        polynomials = [
            NASAPolynomial(coeffs=[2.49197,0.0158706,-1.26272e-05,5.33992e-09,-9.11597e-13,-7584.87,10.6694], Tmin=(298,'K'), Tmax=(1410,'K')),
            NASAPolynomial(coeffs=[6.03579,0.00581722,-1.93207e-06,2.8314e-10,-1.50052e-14,-8584.22,-7.64505], Tmin=(1410,'K'), Tmax=(3500,'K')),
        ],
        Tmin = (298,'K'),
        Tmax = (3500,'K'),
    ),
    shortDesc = """_low T polynomial Tmin changed from 300.0 to 298.0 K when importing to RMG.
C=C=O
_imported from PCI2017/052-Stagni/thermo.txt.""",
    longDesc = 
"""
Formula: C2H2O
Species name in model: CH2CO
_auto-generated from kinetic-models database.
""",
)

entry(
    index = 1,
    label = "C2H3O",
    molecule = 
"""
multiplicity 2
1 O u0 p2 c0 {3,D}
2 C u1 p0 c0 {3,S} {4,S} {5,S}
3 C u0 p0 c0 {1,D} {2,S} {6,S}
4 H u0 p0 c0 {2,S}
5 H u0 p0 c0 {2,S}
6 H u0 p0 c0 {3,S}
""",
    thermo = NASA(
        polynomials = [
            NASAPolynomial(coeffs=[0.215742,0.0278721,-2.67403e-05,1.43321e-08,-3.22099e-12,673.694,22.6662], Tmin=(298,'K'), Tmax=(1030,'K')),
            NASAPolynomial(coeffs=[3.66503,0.0144768,-7.23266e-06,1.7058e-09,-1.56346e-13,-36.8579,5.92342], Tmin=(1030,'K'), Tmax=(3500,'K')),
        ],
        Tmin = (298,'K'),
        Tmax = (3500,'K'),
    ),
    shortDesc = """_low T polynomial Tmin changed from 300.0 to 298.0 K when importing to RMG.
[CH2]C=O
_imported from PCI2017/052-Stagni/thermo.txt.""",
    longDesc = 
"""
Formula: C2H3O
Species name in model: CH2CHO
_auto-generated from kinetic-models database.
""",
)

entry(
    index = 2,
    label = "C4H8",
    molecule = 
"""
1  C u0 p0 c0 {2,S} {3,S} {5,S} {6,S}
2  C u0 p0 c0 {1,S} {7,S} {8,S} {9,S}
3  C u0 p0 c0 {1,S} {4,D} {10,S}
4  C u0 p0 c0 {3,D} {11,S} {12,S}
5  H u0 p0 c0 {1,S}
6  H u0 p0 c0 {1,S}
7  H u0 p0 c0 {2,S}
8  H u0 p0 c0 {2,S}
9  H u0 p0 c0 {2,S}
10 H u0 p0 c0 {3,S}
11 H u0 p0 c0 {4,S}
12 H u0 p0 c0 {4,S}
""",
    thermo = NASA(
        polynomials = [
            NASAPolynomial(coeffs=[-1.05708,0.0463545,-3.2351e-05,1.30416e-08,-2.37314e-12,-1554.78,30.543], Tmin=(298,'K'), Tmax=(1170,'K')),
            NASAPolynomial(coeffs=[2.9871,0.0325283,-1.4625e-05,2.94136e-09,-2.14961e-13,-2501.12,10.3972], Tmin=(1170,'K'), Tmax=(3500,'K')),
        ],
        Tmin = (298,'K'),
        Tmax = (3500,'K'),
    ),
    shortDesc = """_low T polynomial Tmin changed from 300.0 to 298.0 K when importing to RMG.
C=CCC
_imported from PCI2017/052-Stagni/thermo.txt.""",
    longDesc = 
"""
Formula: C4H8
Species name in model: NC4H8
_auto-generated from kinetic-models database.
""",
)

entry(
    index = 3,
    label = "C4H9",
    molecule = 
"""
multiplicity 2
1  C u0 p0 c0 {2,S} {3,S} {5,S} {6,S}
2  C u0 p0 c0 {1,S} {4,S} {7,S} {8,S}
3  C u0 p0 c0 {1,S} {9,S} {10,S} {11,S}
4  C u1 p0 c0 {2,S} {12,S} {13,S}
5  H u0 p0 c0 {1,S}
6  H u0 p0 c0 {1,S}
7  H u0 p0 c0 {2,S}
8  H u0 p0 c0 {2,S}
9  H u0 p0 c0 {3,S}
10 H u0 p0 c0 {3,S}
11 H u0 p0 c0 {3,S}
12 H u0 p0 c0 {4,S}
13 H u0 p0 c0 {4,S}
""",
    thermo = NASA(
        polynomials = [
            NASAPolynomial(coeffs=[-0.276188,0.0494131,-3.93793e-05,2.08222e-08,-5.13034e-12,6858.07,27.9243], Tmin=(298,'K'), Tmax=(950,'K')),
            NASAPolynomial(coeffs=[3.94763,0.0316286,-1.12985e-05,1.11637e-09,5.54032e-14,6055.55,7.7635], Tmin=(950,'K'), Tmax=(3500,'K')),
        ],
        Tmin = (298,'K'),
        Tmax = (3500,'K'),
    ),
    shortDesc = """_low T polynomial Tmin changed from 300.0 to 298.0 K when importing to RMG.
[CH2]CCC
_imported from PCI2017/052-Stagni/thermo.txt.""",
    longDesc = 
"""
Formula: C4H9
Species name in model: NC4H9P
_auto-generated from kinetic-models database.
""",
)

entry(
    index = 4,
    label = "C4H9O2",
    molecule = 
"""
multiplicity 2
1  O u0 p2 c0 {2,S} {5,S}
2  O u1 p2 c0 {1,S}
3  C u0 p0 c0 {4,S} {5,S} {9,S} {10,S}
4  C u0 p0 c0 {3,S} {6,S} {7,S} {8,S}
5  C u0 p0 c0 {1,S} {3,S} {11,S} {12,S}
6  C u0 p0 c0 {4,S} {13,S} {14,S} {15,S}
7  H u0 p0 c0 {4,S}
8  H u0 p0 c0 {4,S}
9  H u0 p0 c0 {3,S}
10 H u0 p0 c0 {3,S}
11 H u0 p0 c0 {5,S}
12 H u0 p0 c0 {5,S}
13 H u0 p0 c0 {6,S}
14 H u0 p0 c0 {6,S}
15 H u0 p0 c0 {6,S}
""",
    thermo = NASA(
        polynomials = [
            NASAPolynomial(coeffs=[0.944282,0.0584166,-4.33881e-05,1.74587e-08,-2.949e-12,-11966.9,25.094], Tmin=(298,'K'), Tmax=(1320,'K')),
            NASAPolynomial(coeffs=[8.9663,0.0341075,-1.57641e-05,3.50716e-09,-3.06663e-13,-14084.7,-15.8347], Tmin=(1320,'K'), Tmax=(3500,'K')),
        ],
        Tmin = (298,'K'),
        Tmax = (3500,'K'),
    ),
    shortDesc = """_low T polynomial Tmin changed from 300.0 to 298.0 K when importing to RMG.
CCCCO[O]
_imported from PCI2017/052-Stagni/thermo.txt.""",
    longDesc = 
"""
Formula: C4H9O2
Species name in model: NC4H9-OO
_auto-generated from kinetic-models database.
""",
)

entry(
    index = 5,
    label = "HO2",
    molecule = 
"""
multiplicity 2
1 O u0 p2 c0 {2,S} {3,S}
2 O u1 p2 c0 {1,S}
3 H u0 p0 c0 {1,S}
""",
    thermo = NASA(
        polynomials = [
            NASAPolynomial(coeffs=[2.85241,0.00540257,-3.80535e-06,1.51268e-09,-2.40354e-13,447.851,9.84484], Tmin=(298,'K'), Tmax=(1540,'K')),
            NASAPolynomial(coeffs=[4.16318,0.00199798,-4.89192e-07,7.71153e-11,-7.30772e-15,44.1349,2.95518], Tmin=(1540,'K'), Tmax=(3500,'K')),
        ],
        Tmin = (298,'K'),
        Tmax = (3500,'K'),
    ),
    shortDesc = """_low T polynomial Tmin changed from 300.0 to 298.0 K when importing to RMG.
[O]O
_imported from PCI2017/052-Stagni/thermo.txt.""",
    longDesc = 
"""
Formula: HO2
Species name in model: HO2
_auto-generated from kinetic-models database.
""",
)

entry(
    index = 6,
    label = "O2",
    molecule = 
"""
multiplicity 3
1 O u1 p2 c0 {2,S}
2 O u1 p2 c0 {1,S}
""",
    thermo = NASA(
        polynomials = [
            NASAPolynomial(coeffs=[3.46035,-0.000885011,5.15281e-06,-5.40712e-09,1.8781e-12,-1029.43,5.02236], Tmin=(298,'K'), Tmax=(760,'K')),
            NASAPolynomial(coeffs=[2.81751,0.00249838,-1.52494e-06,4.50548e-10,-4.87703e-14,-931.713,7.94729], Tmin=(760,'K'), Tmax=(3500,'K')),
        ],
        Tmin = (298,'K'),
        Tmax = (3500,'K'),
    ),
    shortDesc = """_low T polynomial Tmin changed from 300.0 to 298.0 K when importing to RMG.
[O][O]
_imported from PCI2017/052-Stagni/thermo.txt.""",
    longDesc = 
"""
Formula: O2
Species name in model: O2
_auto-generated from kinetic-models database.
""",
)


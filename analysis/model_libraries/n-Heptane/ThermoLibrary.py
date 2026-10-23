#!/usr/bin/env python
# encoding: utf-8

name = "n-Heptane"
shortDesc = "Thermo library for species appearing in shared reactions with Harris-Butane"
longDesc = """
Thermo entries from model n-Heptane
filtered to species that participate in reactions shared with Harris-Butane.
Auto-generated from the kinetic-models database.
"""
entry(
    index = 0,
    label = "C4H10",
    molecule = 
"""
1  C u0 p0 c0 {2,S} {3,S} {5,S} {6,S}
2  C u0 p0 c0 {1,S} {4,S} {7,S} {8,S}
3  C u0 p0 c0 {1,S} {9,S} {10,S} {11,S}
4  C u0 p0 c0 {2,S} {12,S} {13,S} {14,S}
5  H u0 p0 c0 {1,S}
6  H u0 p0 c0 {1,S}
7  H u0 p0 c0 {2,S}
8  H u0 p0 c0 {2,S}
9  H u0 p0 c0 {3,S}
10 H u0 p0 c0 {3,S}
11 H u0 p0 c0 {3,S}
12 H u0 p0 c0 {4,S}
13 H u0 p0 c0 {4,S}
14 H u0 p0 c0 {4,S}
""",
    thermo = NASA(
        polynomials = [
            NASAPolynomial(coeffs=[-0.455757,0.0480323,-2.65498e-05,6.92545e-09,-6.38318e-13,-16896.1,26.4871], Tmin=(298,'K'), Tmax=(1392,'K')),
            NASAPolynomial(coeffs=[12.494,0.0217726,-7.44272e-06,1.15487e-09,-6.69713e-14,-21840.3,-44.5559], Tmin=(1392,'K'), Tmax=(5000,'K')),
        ],
        Tmin = (298,'K'),
        Tmax = (5000,'K'),
    ),
    shortDesc = """8/ 4/ 4 THERM
_low T polynomial Tmin changed from 300.0 to 298.0 K when importing to RMG.
CCCC
_imported from n-Heptane/n_heptane_v3.1_therm.dat.""",
    longDesc = 
"""
Formula: C4H10
Species name in model: C4H10
_auto-generated from kinetic-models database.
""",
)

entry(
    index = 1,
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
            NASAPolynomial(coeffs=[-0.833377,0.0454141,-2.97609e-05,1.03518e-08,-1.51976e-12,-1491.62,29.4328], Tmin=(298,'K'), Tmax=(1391,'K')),
            NASAPolynomial(coeffs=[11.3457,0.0180843,-6.17277e-06,9.56926e-10,-5.54586e-14,-5886.59,-36.4627], Tmin=(1391,'K'), Tmax=(5000,'K')),
        ],
        Tmin = (298,'K'),
        Tmax = (5000,'K'),
    ),
    shortDesc = """6/29/ 4 THERM
_low T polynomial Tmin changed from 300.0 to 298.0 K when importing to RMG.
C=CCC
_imported from n-Heptane/n_heptane_v3.1_therm.dat.""",
    longDesc = 
"""
Formula: C4H8
Species name in model: C4H8-1
_auto-generated from kinetic-models database.
""",
)

entry(
    index = 2,
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
            NASAPolynomial(coeffs=[0.320731,0.0434654,-2.40585e-05,6.28245e-09,-5.80113e-13,7714.91,25.7301], Tmin=(298,'K'), Tmax=(1391,'K')),
            NASAPolynomial(coeffs=[12.078,0.0196265,-6.71302e-06,1.04206e-09,-6.04469e-14,3225.5,-38.7719], Tmin=(1391,'K'), Tmax=(5000,'K')),
        ],
        Tmin = (298,'K'),
        Tmax = (5000,'K'),
    ),
    shortDesc = """8/ 4/ 4 THERM
_low T polynomial Tmin changed from 300.0 to 298.0 K when importing to RMG.
[CH2]CCC
_imported from n-Heptane/n_heptane_v3.1_therm.dat.""",
    longDesc = 
"""
Formula: C4H9
Species name in model: PC4H9
_auto-generated from kinetic-models database.
""",
)

entry(
    index = 3,
    label = "C4H9O2",
    molecule = 
"""
multiplicity 2
1  O u0 p2 c0 {2,S} {4,S}
2  O u1 p2 c0 {1,S}
3  C u0 p0 c0 {4,S} {5,S} {6,S} {7,S}
4  C u0 p0 c0 {1,S} {3,S} {8,S} {9,S}
5  C u0 p0 c0 {3,S} {10,S} {11,S} {12,S}
6  C u0 p0 c0 {3,S} {13,S} {14,S} {15,S}
7  H u0 p0 c0 {3,S}
8  H u0 p0 c0 {4,S}
9  H u0 p0 c0 {4,S}
10 H u0 p0 c0 {5,S}
11 H u0 p0 c0 {5,S}
12 H u0 p0 c0 {5,S}
13 H u0 p0 c0 {6,S}
14 H u0 p0 c0 {6,S}
15 H u0 p0 c0 {6,S}
""",
    thermo = NASA(
        polynomials = [
            NASAPolynomial(coeffs=[1.21434,0.0545388,-3.67002e-05,1.34131e-08,-2.11742e-12,-11848.2,23.4153], Tmin=(298,'K'), Tmax=(1387,'K')),
            NASAPolynomial(coeffs=[15.9741,0.0213535,-7.39001e-06,1.15624e-09,-6.74408e-14,-17232.9,-56.5302], Tmin=(1387,'K'), Tmax=(5000,'K')),
        ],
        Tmin = (298,'K'),
        Tmax = (5000,'K'),
    ),
    shortDesc = """7/19/ 0 THERM
_low T polynomial Tmin changed from 300.0 to 298.0 K when importing to RMG.
CC(C)CO[O]
_imported from n-Heptane/n_heptane_v3.1_therm.dat.""",
    longDesc = 
"""
Formula: C4H9O2
Species name in model: IC4H9O2
_auto-generated from kinetic-models database.
""",
)

entry(
    index = 4,
    label = "CH3",
    molecule = 
"""
multiplicity 2
1 C u1 p0 c0 {2,S} {3,S} {4,S}
2 H u0 p0 c0 {1,S}
3 H u0 p0 c0 {1,S}
4 H u0 p0 c0 {1,S}
""",
    thermo = NASA(
        polynomials = [
            NASAPolynomial(coeffs=[3.43858,0.00407753,3.19831e-07,-9.47669e-10,2.21828e-13,16316.4,2.52807], Tmin=(298,'K'), Tmax=(1389,'K')),
            NASAPolynomial(coeffs=[3.51281,0.00511413,-1.67632e-06,2.52495e-10,-1.43303e-14,16123.8,1.62436], Tmin=(1389,'K'), Tmax=(5000,'K')),
        ],
        Tmin = (298,'K'),
        Tmax = (5000,'K'),
    ),
    shortDesc = """_low T polynomial Tmin changed from 300.0 to 298.0 K when importing to RMG.
[CH3]
_imported from n-Heptane/n_heptane_v3.1_therm.dat.""",
    longDesc = 
"""
Formula: CH3
Species name in model: CH3
_auto-generated from kinetic-models database.
""",
)

entry(
    index = 5,
    label = "CH4",
    molecule = 
"""
1 C u0 p0 c0 {2,S} {3,S} {4,S} {5,S}
2 H u0 p0 c0 {1,S}
3 H u0 p0 c0 {1,S}
4 H u0 p0 c0 {1,S}
5 H u0 p0 c0 {1,S}
""",
    thermo = NASA(
        polynomials = [
            NASAPolynomial(coeffs=[3.72113,-0.00250293,1.90247e-05,-1.46871e-08,3.43791e-12,-10142.4,1.22777], Tmin=(298,'K'), Tmax=(1462,'K')),
            NASAPolynomial(coeffs=[4.09618,0.00744331,-2.63872e-06,4.19578e-10,-2.47508e-14,-11383.6,-4.67561], Tmin=(1462,'K'), Tmax=(5000,'K')),
        ],
        Tmin = (298,'K'),
        Tmax = (5000,'K'),
    ),
    shortDesc = """29/11/04
_low T polynomial Tmin changed from 300.0 to 298.0 K when importing to RMG.
C
_imported from n-Heptane/n_heptane_v3.1_therm.dat.""",
    longDesc = 
"""
Formula: CH4
Species name in model: CH4
_auto-generated from kinetic-models database.
""",
)

entry(
    index = 6,
    label = "H",
    molecule = 
"""
multiplicity 2
1 H u1 p0 c0
""",
    thermo = NASA(
        polynomials = [
            NASAPolynomial(coeffs=[2.5,0,0,0,0,25471.6,-0.460118], Tmin=(298,'K'), Tmax=(1000,'K')),
            NASAPolynomial(coeffs=[2.5,0,0,0,0,25471.6,-0.460118], Tmin=(1000,'K'), Tmax=(5000,'K')),
        ],
        Tmin = (298,'K'),
        Tmax = (5000,'K'),
    ),
    shortDesc = """120186
_low T polynomial Tmin changed from 300.0 to 298.0 K when importing to RMG.
[H]
_imported from n-Heptane/n_heptane_v3.1_therm.dat.""",
    longDesc = 
"""
Formula: H
Species name in model: H
_auto-generated from kinetic-models database.
""",
)

entry(
    index = 7,
    label = "H2",
    molecule = 
"""
1 H u0 p0 c0 {2,S}
2 H u0 p0 c0 {1,S}
""",
    thermo = NASA(
        polynomials = [
            NASAPolynomial(coeffs=[3.29812,0.000824944,-8.14302e-07,-9.47543e-11,4.13487e-13,-1012.52,-3.29409], Tmin=(298,'K'), Tmax=(1000,'K')),
            NASAPolynomial(coeffs=[2.99142,0.000700064,-5.63383e-08,-9.23158e-12,1.58275e-15,-835.034,-1.35511], Tmin=(1000,'K'), Tmax=(5000,'K')),
        ],
        Tmin = (298,'K'),
        Tmax = (5000,'K'),
    ),
    shortDesc = """121286
_low T polynomial Tmin changed from 300.0 to 298.0 K when importing to RMG.
[H][H]
_imported from n-Heptane/n_heptane_v3.1_therm.dat.""",
    longDesc = 
"""
Formula: H2
Species name in model: H2
_auto-generated from kinetic-models database.
""",
)

entry(
    index = 8,
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
            NASAPolynomial(coeffs=[4.3018,-0.00474912,2.11583e-05,-2.42764e-08,9.29225e-12,294.808,3.71666], Tmin=(200,'K'), Tmax=(1000,'K')),
            NASAPolynomial(coeffs=[4.01721,0.00223982,-6.33658e-07,1.14246e-10,-1.07909e-14,111.857,3.7851], Tmin=(1000,'K'), Tmax=(3500,'K')),
        ],
        Tmin = (200,'K'),
        Tmax = (3500,'K'),
    ),
    shortDesc = """L 5/89.
[O]O
_imported from n-Heptane/n_heptane_v3.1_therm.dat.""",
    longDesc = 
"""
Formula: HO2
Species name in model: HO2
_auto-generated from kinetic-models database.
""",
)

entry(
    index = 9,
    label = "O2",
    molecule = 
"""
multiplicity 3
1 O u1 p2 c0 {2,S}
2 O u1 p2 c0 {1,S}
""",
    thermo = NASA(
        polynomials = [
            NASAPolynomial(coeffs=[3.21294,0.00112749,-5.75615e-07,1.31388e-09,-8.76855e-13,-1005.25,6.03474], Tmin=(298,'K'), Tmax=(1000,'K')),
            NASAPolynomial(coeffs=[3.69758,0.00061352,-1.25884e-07,1.77528e-11,-1.13644e-15,-1233.93,3.18917], Tmin=(1000,'K'), Tmax=(5000,'K')),
        ],
        Tmin = (298,'K'),
        Tmax = (5000,'K'),
    ),
    shortDesc = """121386
_low T polynomial Tmin changed from 300.0 to 298.0 K when importing to RMG.
[O][O]
_imported from n-Heptane/n_heptane_v3.1_therm.dat.""",
    longDesc = 
"""
Formula: O2
Species name in model: O2
_auto-generated from kinetic-models database.
""",
)


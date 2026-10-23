#!/usr/bin/env python
# encoding: utf-8

name = "PCI2017/032-Cheng"
shortDesc = "Thermo library for species appearing in shared reactions with Harris-Butane"
longDesc = """
Thermo entries from model PCI2017/032-Cheng
filtered to species that participate in reactions shared with Harris-Butane.
Auto-generated from the kinetic-models database.
"""
entry(
    index = 0,
    label = "C2H4",
    molecule = 
"""
1 C u0 p0 c0 {2,D} {3,S} {4,S}
2 C u0 p0 c0 {1,D} {5,S} {6,S}
3 H u0 p0 c0 {1,S}
4 H u0 p0 c0 {1,S}
5 H u0 p0 c0 {2,S}
6 H u0 p0 c0 {2,S}
""",
    thermo = NASA(
        polynomials = [
            NASAPolynomial(coeffs=[3.9592,-0.00757051,5.7099e-05,-6.91588e-08,2.69884e-11,5089.78,4.0973], Tmin=(200,'K'), Tmax=(1000,'K')),
            NASAPolynomial(coeffs=[3.99183,0.0104834,-3.71721e-06,5.94628e-10,-3.5363e-14,4268.66,-0.269082], Tmin=(1000,'K'), Tmax=(6000,'K')),
        ],
        Tmin = (200,'K'),
        Tmax = (6000,'K'),
    ),
    shortDesc = """g 1/00.
C=C
_imported from PCI2017/032-Cheng/thermo.txt.""",
    longDesc = 
"""
Formula: C2H4
Species name in model: c2h4
_auto-generated from kinetic-models database.
""",
)

entry(
    index = 1,
    label = "C2H5",
    molecule = 
"""
multiplicity 2
1 C u0 p0 c0 {2,S} {3,S} {4,S} {5,S}
2 C u1 p0 c0 {1,S} {6,S} {7,S}
3 H u0 p0 c0 {1,S}
4 H u0 p0 c0 {1,S}
5 H u0 p0 c0 {1,S}
6 H u0 p0 c0 {2,S}
7 H u0 p0 c0 {2,S}
""",
    thermo = NASA(
        polynomials = [
            NASAPolynomial(coeffs=[1.3273,0.0176657,-6.14927e-06,-3.01143e-10,4.38618e-13,13428.4,17.1789], Tmin=(298,'K'), Tmax=(1387,'K')),
            NASAPolynomial(coeffs=[5.88784,0.0103077,-3.46844e-06,5.32499e-10,-3.06513e-14,11506.5,-8.49652], Tmin=(1387,'K'), Tmax=(5000,'K')),
        ],
        Tmin = (298,'K'),
        Tmax = (5000,'K'),
    ),
    shortDesc = """8/ 4/ 4 therm
_low T polynomial Tmin changed from 300.0 to 298.0 K when importing to RMG.
C[CH2]
_imported from PCI2017/032-Cheng/thermo.txt.""",
    longDesc = 
"""
Formula: C2H5
Species name in model: c2h5
_auto-generated from kinetic-models database.
""",
)

entry(
    index = 2,
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
    shortDesc = """8/ 4/ 4 therm
_low T polynomial Tmin changed from 300.0 to 298.0 K when importing to RMG.
CCCC
_imported from PCI2017/032-Cheng/thermo.txt.""",
    longDesc = 
"""
Formula: C4H10
Species name in model: c4h10
_auto-generated from kinetic-models database.
""",
)

entry(
    index = 3,
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
            NASAPolynomial(coeffs=[5.13226,0.00533863,6.02929e-05,-7.60365e-08,2.87325e-11,-2167.18,3.82937], Tmin=(200,'K'), Tmax=(1000,'K')),
            NASAPolynomial(coeffs=[7.86795,0.0224449,-8.07705e-06,1.3018e-09,-7.77958e-14,-4238.53,-16.5663], Tmin=(1000,'K'), Tmax=(6000,'K')),
        ],
        Tmin = (200,'K'),
        Tmax = (6000,'K'),
    ),
    shortDesc = """t05/09.
C=CCC
_imported from PCI2017/032-Cheng/thermo.txt.""",
    longDesc = 
"""
Formula: C4H8
Species name in model: c4h8-1
_auto-generated from kinetic-models database.
""",
)

entry(
    index = 4,
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
    shortDesc = """8/ 4/ 4 therm
_low T polynomial Tmin changed from 300.0 to 298.0 K when importing to RMG.
[CH2]CCC
_imported from PCI2017/032-Cheng/thermo.txt.""",
    longDesc = 
"""
Formula: C4H9
Species name in model: pc4h9
_auto-generated from kinetic-models database.
""",
)

entry(
    index = 5,
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
    shortDesc = """7/19/ 0 therm
_low T polynomial Tmin changed from 300.0 to 298.0 K when importing to RMG.
CC(C)CO[O]
_imported from PCI2017/032-Cheng/thermo.txt.""",
    longDesc = 
"""
Formula: C4H9O2
Species name in model: ic4h9o2
_auto-generated from kinetic-models database.
""",
)

entry(
    index = 6,
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
            NASAPolynomial(coeffs=[3.65718,0.0021266,5.45839e-06,-6.6181e-09,2.46571e-12,16422.7,1.67354], Tmin=(200,'K'), Tmax=(1000,'K')),
            NASAPolynomial(coeffs=[2.97812,0.00579785,-1.97558e-06,3.07298e-10,-1.79174e-14,16509.5,4.72248], Tmin=(1000,'K'), Tmax=(6000,'K')),
        ],
        Tmin = (200,'K'),
        Tmax = (6000,'K'),
    ),
    shortDesc = """iu0702.
[CH3]
_imported from PCI2017/032-Cheng/thermo.txt.""",
    longDesc = 
"""
Formula: CH3
Species name in model: ch3
_auto-generated from kinetic-models database.
""",
)

entry(
    index = 7,
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
            NASAPolynomial(coeffs=[5.14911,-0.0136622,4.91454e-05,-4.84247e-08,1.66603e-11,-10246.6,-4.63849], Tmin=(200,'K'), Tmax=(1000,'K')),
            NASAPolynomial(coeffs=[1.65326,0.0100263,-3.31661e-06,5.36483e-10,-3.14697e-14,-10009.6,9.90506], Tmin=(1000,'K'), Tmax=(6000,'K')),
        ],
        Tmin = (200,'K'),
        Tmax = (6000,'K'),
    ),
    shortDesc = """g 8/99.
C
_imported from PCI2017/032-Cheng/thermo.txt.""",
    longDesc = 
"""
Formula: CH4
Species name in model: ch4
_auto-generated from kinetic-models database.
""",
)

entry(
    index = 8,
    label = "H",
    molecule = 
"""
multiplicity 2
1 H u1 p0 c0
""",
    thermo = NASA(
        polynomials = [
            NASAPolynomial(coeffs=[2.5,0,0,0,0,25473.7,-0.446683], Tmin=(200,'K'), Tmax=(1000,'K')),
            NASAPolynomial(coeffs=[2.5,0,0,0,0,25473.7,-0.446683], Tmin=(1000,'K'), Tmax=(6000,'K')),
        ],
        Tmin = (200,'K'),
        Tmax = (6000,'K'),
    ),
    shortDesc = """l 6/94
version: aramcomech_1.0
authors: w. k. metcalfe, s. burke, h. j. curran
website: http://c3.nuigalway.ie/.
[H]
_imported from PCI2017/032-Cheng/thermo.txt.""",
    longDesc = 
"""
Formula: H
Species name in model: h
_auto-generated from kinetic-models database.
""",
)

entry(
    index = 9,
    label = "H2",
    molecule = 
"""
1 H u0 p0 c0 {2,S}
2 H u0 p0 c0 {1,S}
""",
    thermo = NASA(
        polynomials = [
            NASAPolynomial(coeffs=[2.34433,0.00798052,-1.94782e-05,2.01572e-08,-7.37612e-12,-917.935,0.68301], Tmin=(200,'K'), Tmax=(1000,'K')),
            NASAPolynomial(coeffs=[2.93287,0.000826608,-1.46402e-07,1.541e-11,-6.88805e-16,-813.066,-1.02433], Tmin=(1000,'K'), Tmax=(6000,'K')),
        ],
        Tmin = (200,'K'),
        Tmax = (6000,'K'),
    ),
    shortDesc = """tpis78.
[H][H]
_imported from PCI2017/032-Cheng/thermo.txt.""",
    longDesc = 
"""
Formula: H2
Species name in model: h2
_auto-generated from kinetic-models database.
""",
)

entry(
    index = 10,
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
            NASAPolynomial(coeffs=[4.3018,-0.00474912,2.11583e-05,-2.42764e-08,9.29225e-12,264.018,3.71666], Tmin=(200,'K'), Tmax=(1000,'K')),
            NASAPolynomial(coeffs=[4.17229,0.00188118,-3.46277e-07,1.94658e-11,1.76257e-16,31.0207,2.95768], Tmin=(1000,'K'), Tmax=(5000,'K')),
        ],
        Tmin = (200,'K'),
        Tmax = (5000,'K'),
    ),
    shortDesc = """t 1/09.
[O]O
_imported from PCI2017/032-Cheng/thermo.txt.""",
    longDesc = 
"""
Formula: HO2
Species name in model: ho2
_auto-generated from kinetic-models database.
""",
)

entry(
    index = 11,
    label = "O2",
    molecule = 
"""
multiplicity 3
1 O u1 p2 c0 {2,S}
2 O u1 p2 c0 {1,S}
""",
    thermo = NASA(
        polynomials = [
            NASAPolynomial(coeffs=[3.78246,-0.00299673,9.8473e-06,-9.6813e-09,3.24373e-12,-1063.94,3.65768], Tmin=(200,'K'), Tmax=(1000,'K')),
            NASAPolynomial(coeffs=[3.66096,0.000656366,-1.4115e-07,2.05798e-11,-1.29913e-15,-1215.98,3.41536], Tmin=(1000,'K'), Tmax=(6000,'K')),
        ],
        Tmin = (200,'K'),
        Tmax = (6000,'K'),
    ),
    shortDesc = """rus 89.
[O][O]
_imported from PCI2017/032-Cheng/thermo.txt.""",
    longDesc = 
"""
Formula: O2
Species name in model: o2
_auto-generated from kinetic-models database.
""",
)


#!/usr/bin/env python
# encoding: utf-8

name = "PCI2013/401-Liu"
shortDesc = "Thermo library for species appearing in shared reactions with Harris-Butane"
longDesc = """
Thermo entries from model PCI2013/401-Liu
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
_imported from PCI2013/401-Liu/thermo.txt.""",
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
_imported from PCI2013/401-Liu/thermo.txt.""",
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
_imported from PCI2013/401-Liu/thermo.txt.""",
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
            NASAPolynomial(coeffs=[1.94364,0.0515513,-3.28284e-05,1.13065e-08,-1.70119e-12,-10835.8,21.3503], Tmin=(298,'K'), Tmax=(1385,'K')),
            NASAPolynomial(coeffs=[15.7845,0.0215211,-7.44909e-06,1.16558e-09,-6.79886e-14,-16014.6,-54.0389], Tmin=(1385,'K'), Tmax=(5000,'K')),
        ],
        Tmin = (298,'K'),
        Tmax = (5000,'K'),
    ),
    shortDesc = """7/19/ 0 THERM
_low T polynomial Tmin changed from 300.0 to 298.0 K when importing to RMG.
CCCCO[O]
_imported from PCI2013/401-Liu/thermo.txt.""",
    longDesc = 
"""
Formula: C4H9O2
Species name in model: PC4H9O2
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
            NASAPolynomial(coeffs=[3.65718,0.0021266,5.45839e-06,-6.6181e-09,2.46571e-12,16422.7,1.67354], Tmin=(200,'K'), Tmax=(1000,'K')),
            NASAPolynomial(coeffs=[2.97812,0.00579785,-1.97558e-06,3.07298e-10,-1.79174e-14,16509.5,4.72248], Tmin=(1000,'K'), Tmax=(6000,'K')),
        ],
        Tmin = (200,'K'),
        Tmax = (6000,'K'),
    ),
    shortDesc = """IU0702.
[CH3]
_imported from PCI2013/401-Liu/thermo.txt.""",
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
            NASAPolynomial(coeffs=[5.14826,-0.0137002,4.93749e-05,-4.91952e-08,1.70097e-11,-10245.3,-4.63323], Tmin=(200,'K'), Tmax=(1000,'K')),
            NASAPolynomial(coeffs=[1.91179,0.00960268,-3.38388e-06,5.38797e-10,-3.19307e-14,-10099.2,8.48242], Tmin=(1000,'K'), Tmax=(6000,'K')),
        ],
        Tmin = (200,'K'),
        Tmax = (6000,'K'),
    ),
    shortDesc = """RRHO       g 8/99.
C
_imported from PCI2013/401-Liu/thermo.txt.""",
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
            NASAPolynomial(coeffs=[2.5,0,0,0,0,25473.7,-0.446683], Tmin=(200,'K'), Tmax=(1000,'K')),
            NASAPolynomial(coeffs=[2.5,0,0,0,0,25473.7,-0.446683], Tmin=(1000,'K'), Tmax=(6000,'K')),
        ],
        Tmin = (200,'K'),
        Tmax = (6000,'K'),
    ),
    shortDesc = """L 6/94.
[H]
_imported from PCI2013/401-Liu/thermo.txt.""",
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
            NASAPolynomial(coeffs=[2.34433,0.00798052,-1.94782e-05,2.01572e-08,-7.37612e-12,-917.935,0.68301], Tmin=(200,'K'), Tmax=(1000,'K')),
            NASAPolynomial(coeffs=[2.93287,0.000826608,-1.46402e-07,1.541e-11,-6.88805e-16,-813.066,-1.02433], Tmin=(1000,'K'), Tmax=(6000,'K')),
        ],
        Tmin = (200,'K'),
        Tmax = (6000,'K'),
    ),
    shortDesc = """REF ELEMENT    tpis78.
[H][H]
_imported from PCI2013/401-Liu/thermo.txt.""",
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
            NASAPolynomial(coeffs=[4.3018,-0.00474912,2.11583e-05,-2.42764e-08,9.29225e-12,264.018,3.71666], Tmin=(200,'K'), Tmax=(1000,'K')),
            NASAPolynomial(coeffs=[4.17229,0.00188118,-3.46277e-07,1.94658e-11,1.76257e-16,31.0207,2.95768], Tmin=(1000,'K'), Tmax=(5000,'K')),
        ],
        Tmin = (200,'K'),
        Tmax = (5000,'K'),
    ),
    shortDesc = """T 1/09.
[O]O
_imported from PCI2013/401-Liu/thermo.txt.""",
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
            NASAPolynomial(coeffs=[3.78246,-0.00299673,9.8473e-06,-9.6813e-09,3.24373e-12,-1063.94,3.65768], Tmin=(200,'K'), Tmax=(1000,'K')),
            NASAPolynomial(coeffs=[3.66096,0.000656366,-1.4115e-07,2.05798e-11,-1.29913e-15,-1215.98,3.41536], Tmin=(1000,'K'), Tmax=(6000,'K')),
        ],
        Tmin = (200,'K'),
        Tmax = (6000,'K'),
    ),
    shortDesc = """REF ELEMENT    TPIS89.
[O][O]
_imported from PCI2013/401-Liu/thermo.txt.""",
    longDesc = 
"""
Formula: O2
Species name in model: O2
_auto-generated from kinetic-models database.
""",
)


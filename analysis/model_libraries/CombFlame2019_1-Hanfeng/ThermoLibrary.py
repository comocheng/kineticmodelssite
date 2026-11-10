#!/usr/bin/env python
# encoding: utf-8

name = "CombFlame2019/1-Hanfeng"
shortDesc = "Thermo library for species appearing in shared reactions with Harris-Butane"
longDesc = """
Thermo entries from model CombFlame2019/1-Hanfeng
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
            NASAPolynomial(coeffs=[2.13584,0.0181189,-1.73947e-05,9.34398e-09,-2.01458e-12,-7042.92,12.2156], Tmin=(200,'K'), Tmax=(1000,'K')),
            NASAPolynomial(coeffs=[4.5113,0.0090036,-4.1694e-06,9.23346e-10,-7.94838e-14,-7551.05,0.632247], Tmin=(1000,'K'), Tmax=(3500,'K')),
        ],
        Tmin = (200,'K'),
        Tmax = (3500,'K'),
    ),
    shortDesc = """L-5-90.
C=C=O
_imported from CombFlame2019/1-Hanfeng/thermo.dat.""",
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
2 C u0 p0 c0 {3,S} {4,S} {5,S} {6,S}
3 C u1 p0 c0 {1,D} {2,S}
4 H u0 p0 c0 {2,S}
5 H u0 p0 c0 {2,S}
6 H u0 p0 c0 {2,S}
""",
    thermo = NASA(
        polynomials = [
            NASAPolynomial(coeffs=[4.16343,-0.000232616,3.42678e-05,-4.41052e-08,1.72756e-11,-2657.45,7.34683], Tmin=(200,'K'), Tmax=(1000,'K')),
            NASAPolynomial(coeffs=[5.94477,0.00786672,-2.88659e-06,4.72709e-10,-2.85999e-14,-3787.31,-5.01368], Tmin=(1000,'K'), Tmax=(6000,'K')),
        ],
        Tmin = (200,'K'),
        Tmax = (6000,'K'),
    ),
    shortDesc = """T-9-92.
C[C]=O
_imported from CombFlame2019/1-Hanfeng/thermo.dat.""",
    longDesc = 
"""
Formula: C2H3O
Species name in model: CH3CO
_auto-generated from kinetic-models database.
""",
)

entry(
    index = 2,
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
            NASAPolynomial(coeffs=[3.9592,-0.00757052,5.7099e-05,-6.91589e-08,2.69884e-11,5089.78,4.09733], Tmin=(200,'K'), Tmax=(1000,'K')),
            NASAPolynomial(coeffs=[2.03611,0.0146454,-6.71078e-06,1.47223e-09,-1.25706e-13,4939.89,10.3054], Tmin=(1000,'K'), Tmax=(3500,'K')),
        ],
        Tmin = (200,'K'),
        Tmax = (3500,'K'),
    ),
    shortDesc = """L-1-91.
C=C
_imported from CombFlame2019/1-Hanfeng/thermo.dat.""",
    longDesc = 
"""
Formula: C2H4
Species name in model: C2H4
_auto-generated from kinetic-models database.
""",
)

entry(
    index = 3,
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
            NASAPolynomial(coeffs=[4.30647,-0.00418659,4.97143e-05,-5.99127e-08,2.30509e-11,12841.6,4.70721], Tmin=(200,'K'), Tmax=(1000,'K')),
            NASAPolynomial(coeffs=[1.95466,0.0173973,-7.98207e-06,1.75218e-09,-1.49642e-13,12857.5,13.4624], Tmin=(1000,'K'), Tmax=(3500,'K')),
        ],
        Tmin = (200,'K'),
        Tmax = (3500,'K'),
    ),
    shortDesc = """L12-92.
C[CH2]
_imported from CombFlame2019/1-Hanfeng/thermo.dat.""",
    longDesc = 
"""
Formula: C2H5
Species name in model: C2H5
_auto-generated from kinetic-models database.
""",
)

entry(
    index = 4,
    label = "C4H10",
    molecule = 
"""
1  C u0 p0 c0 {2,S} {3,S} {4,S} {5,S}
2  C u0 p0 c0 {1,S} {6,S} {7,S} {8,S}
3  C u0 p0 c0 {1,S} {9,S} {10,S} {11,S}
4  C u0 p0 c0 {1,S} {12,S} {13,S} {14,S}
5  H u0 p0 c0 {1,S}
6  H u0 p0 c0 {2,S}
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
            NASAPolynomial(coeffs=[0.541095,0.0378603,5.54598e-06,-3.05001e-08,1.40334e-11,-17977.6,21.1509], Tmin=(298,'K'), Tmax=(1000,'K')),
            NASAPolynomial(coeffs=[10.8462,0.0233384,-7.7834e-06,1.13938e-09,-5.99183e-14,-21669.9,-35.8706], Tmin=(1000,'K'), Tmax=(3000,'K')),
        ],
        Tmin = (298,'K'),
        Tmax = (3000,'K'),
    ),
    shortDesc = """P11-94
_low T polynomial Tmin changed from 300.0 to 298.0 K when importing to RMG.
CC(C)C
_imported from CombFlame2019/1-Hanfeng/thermo.dat.""",
    longDesc = 
"""
Formula: C4H10
Species name in model: iC4H10
_auto-generated from kinetic-models database.
""",
)

entry(
    index = 5,
    label = "C4H9",
    molecule = 
"""
multiplicity 2
1  C u0 p0 c0 {4,S} {5,S} {6,S} {7,S}
2  C u0 p0 c0 {4,S} {8,S} {9,S} {10,S}
3  C u0 p0 c0 {4,S} {11,S} {12,S} {13,S}
4  C u1 p0 c0 {1,S} {2,S} {3,S}
5  H u0 p0 c0 {1,S}
6  H u0 p0 c0 {1,S}
7  H u0 p0 c0 {1,S}
8  H u0 p0 c0 {2,S}
9  H u0 p0 c0 {2,S}
10 H u0 p0 c0 {2,S}
11 H u0 p0 c0 {3,S}
12 H u0 p0 c0 {3,S}
13 H u0 p0 c0 {3,S}
""",
    thermo = NASA(
        polynomials = [
            NASAPolynomial(coeffs=[0.961676,0.0257359,1.5609e-05,-2.66565e-08,8.9418e-12,4656.44,24.8054], Tmin=(298,'K'), Tmax=(1000,'K')),
            NASAPolynomial(coeffs=[7.66073,0.0238794,-8.08904e-06,1.20575e-09,-6.50098e-14,1620.76,-14.8003], Tmin=(1000,'K'), Tmax=(3000,'K')),
        ],
        Tmin = (298,'K'),
        Tmax = (3000,'K'),
    ),
    shortDesc = """P11-94
_low T polynomial Tmin changed from 300.0 to 298.0 K when importing to RMG.
C[C](C)C
_imported from CombFlame2019/1-Hanfeng/thermo.dat.""",
    longDesc = 
"""
Formula: C4H9
Species name in model: tC4H9
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
            NASAPolynomial(coeffs=[3.43858,0.00407753,3.19831e-07,-9.47669e-10,2.21828e-13,16316.4,2.52807], Tmin=(298,'K'), Tmax=(1389,'K')),
            NASAPolynomial(coeffs=[3.51281,0.00511413,-1.67632e-06,2.52495e-10,-1.43303e-14,16123.8,1.62436], Tmin=(1389,'K'), Tmax=(5000,'K')),
        ],
        Tmin = (298,'K'),
        Tmax = (5000,'K'),
    ),
    shortDesc = """_low T polynomial Tmin changed from 300.0 to 298.0 K when importing to RMG.
[CH3]
_imported from CombFlame2019/1-Hanfeng/thermo.dat.""",
    longDesc = 
"""
Formula: CH3
Species name in model: CH3
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
            NASAPolynomial(coeffs=[3.72113,-0.00250293,1.90247e-05,-1.46871e-08,3.43791e-12,-10142.4,1.22777], Tmin=(298,'K'), Tmax=(1462,'K')),
            NASAPolynomial(coeffs=[4.09618,0.00744331,-2.63872e-06,4.19578e-10,-2.47508e-14,-11383.6,-4.67561], Tmin=(1462,'K'), Tmax=(5000,'K')),
        ],
        Tmin = (298,'K'),
        Tmax = (5000,'K'),
    ),
    shortDesc = """_low T polynomial Tmin changed from 300.0 to 298.0 K when importing to RMG.
C
_imported from CombFlame2019/1-Hanfeng/thermo.dat.""",
    longDesc = 
"""
Formula: CH4
Species name in model: CH4
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
            NASAPolynomial(coeffs=[2.5,0,0,0,0,25471.6,-0.460118], Tmin=(298,'K'), Tmax=(1000,'K')),
            NASAPolynomial(coeffs=[2.5,0,0,0,0,25471.6,-0.460118], Tmin=(1000,'K'), Tmax=(5000,'K')),
        ],
        Tmin = (298,'K'),
        Tmax = (5000,'K'),
    ),
    shortDesc = """120186
_low T polynomial Tmin changed from 300.0 to 298.0 K when importing to RMG.
[H]
_imported from CombFlame2019/1-Hanfeng/thermo.dat.""",
    longDesc = 
"""
Formula: H
Species name in model: H
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
            NASAPolynomial(coeffs=[3.29812,0.000824944,-8.14302e-07,-9.47543e-11,4.13487e-13,-1012.52,-3.29409], Tmin=(298,'K'), Tmax=(1000,'K')),
            NASAPolynomial(coeffs=[2.99142,0.000700064,-5.63383e-08,-9.23158e-12,1.58275e-15,-835.034,-1.35511], Tmin=(1000,'K'), Tmax=(5000,'K')),
        ],
        Tmin = (298,'K'),
        Tmax = (5000,'K'),
    ),
    shortDesc = """121286
_low T polynomial Tmin changed from 300.0 to 298.0 K when importing to RMG.
[H][H]
_imported from CombFlame2019/1-Hanfeng/thermo.dat.""",
    longDesc = 
"""
Formula: H2
Species name in model: H2
_auto-generated from kinetic-models database.
""",
)

entry(
    index = 10,
    label = "H2O2",
    molecule = 
"""
1 O u0 p2 c0 {2,S} {3,S}
2 O u0 p2 c0 {1,S} {4,S}
3 H u0 p0 c0 {1,S}
4 H u0 p0 c0 {2,S}
""",
    thermo = NASA(
        polynomials = [
            NASAPolynomial(coeffs=[3.38875,0.00656923,-1.48501e-07,-4.62581e-09,2.47151e-12,-17663.2,6.78536], Tmin=(298,'K'), Tmax=(1000,'K')),
            NASAPolynomial(coeffs=[4.57317,0.00433614,-1.47469e-06,2.3489e-10,-1.43165e-14,-18007,0.501137], Tmin=(1000,'K'), Tmax=(5000,'K')),
        ],
        Tmin = (298,'K'),
        Tmax = (5000,'K'),
    ),
    shortDesc = """120186
_low T polynomial Tmin changed from 300.0 to 298.0 K when importing to RMG.
OO
_imported from CombFlame2019/1-Hanfeng/thermo.dat.""",
    longDesc = 
"""
Formula: H2O2
Species name in model: H2O2
_auto-generated from kinetic-models database.
""",
)

entry(
    index = 11,
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
    shortDesc = """L-5-89.
[O]O
_imported from CombFlame2019/1-Hanfeng/thermo.dat.""",
    longDesc = 
"""
Formula: HO2
Species name in model: HO2
_auto-generated from kinetic-models database.
""",
)

entry(
    index = 12,
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
_imported from CombFlame2019/1-Hanfeng/thermo.dat.""",
    longDesc = 
"""
Formula: O2
Species name in model: O2
_auto-generated from kinetic-models database.
""",
)


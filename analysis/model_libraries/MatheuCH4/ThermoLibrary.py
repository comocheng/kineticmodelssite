#!/usr/bin/env python
# encoding: utf-8

name = "MatheuCH4"
shortDesc = "Thermo library for species appearing in shared reactions with Harris-Butane"
longDesc = """
Thermo entries from model MatheuCH4
filtered to species that participate in reactions shared with Harris-Butane.
Auto-generated from the kinetic-models database.
"""
entry(
    index = 0,
    label = "C3H5",
    molecule = 
"""
multiplicity 2
1 C u0 p0 c0 {2,S} {4,S} {5,S} {6,S}
2 C u0 p0 c0 {1,S} {3,D} {7,S}
3 C u1 p0 c0 {2,D} {8,S}
4 H u0 p0 c0 {1,S}
5 H u0 p0 c0 {1,S}
6 H u0 p0 c0 {1,S}
7 H u0 p0 c0 {2,S}
8 H u0 p0 c0 {3,S}
""",
    thermo = NASA(
        polynomials = [
            NASAPolynomial(coeffs=[2.2361,0.0163872,7.66397e-06,-1.93648e-08,8.41555e-12,30173.5,14.8061], Tmin=(298,'K'), Tmax=(1000,'K')),
            NASAPolynomial(coeffs=[6.13422,0.013325,-4.86452e-06,8.37739e-10,-5.51614e-14,28626.2,-7.41121], Tmin=(1000,'K'), Tmax=(5000,'K')),
        ],
        Tmin = (298,'K'),
        Tmax = (5000,'K'),
    ),
    shortDesc = """Low T polynomial Tmin changed from 300.0 to 298.0 K when importing to RMG.
[CH]=CC
Imported from MatheuCH4/Matheu_CH4_pyrolysis_gas_kinetics.inp.""",
    longDesc = 
"""
Formula: C3H5
Species name in model: C3H5
_auto-generated from kinetic-models database.
""",
)

entry(
    index = 1,
    label = "C3H6",
    molecule = 
"""
1 C u0 p0 c0 {2,S} {4,S} {5,S} {6,S}
2 C u0 p0 c0 {1,S} {3,D} {7,S}
3 C u0 p0 c0 {2,D} {8,S} {9,S}
4 H u0 p0 c0 {1,S}
5 H u0 p0 c0 {1,S}
6 H u0 p0 c0 {1,S}
7 H u0 p0 c0 {2,S}
8 H u0 p0 c0 {3,S}
9 H u0 p0 c0 {3,S}
""",
    thermo = NASA(
        polynomials = [
            NASAPolynomial(coeffs=[1.45752,0.0211423,4.0468e-06,-1.6319e-08,7.04752e-12,1074.02,17.3995], Tmin=(298,'K'), Tmax=(1000,'K')),
            NASAPolynomial(coeffs=[6.7214,0.0149318,-4.96524e-06,7.25108e-10,-3.80015e-14,-924.531,-12.1556], Tmin=(1000,'K'), Tmax=(5000,'K')),
        ],
        Tmin = (298,'K'),
        Tmax = (5000,'K'),
    ),
    shortDesc = """Low T polynomial Tmin changed from 300.0 to 298.0 K when importing to RMG.
C=CC
Imported from MatheuCH4/Matheu_CH4_pyrolysis_gas_kinetics.inp.""",
    longDesc = 
"""
Formula: C3H6
Species name in model: C3H6
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
            NASAPolynomial(coeffs=[-0.831372,0.0452581,-2.93659e-05,1.0022e-08,-1.43192e-12,-1578.75,29.5084], Tmin=(298,'K'), Tmax=(1392,'K')),
            NASAPolynomial(coeffs=[11.3509,0.0180618,-6.16093e-06,9.54653e-10,-5.5309e-14,-5978.71,-36.4369], Tmin=(1392,'K'), Tmax=(5000,'K')),
        ],
        Tmin = (298,'K'),
        Tmax = (5000,'K'),
    ),
    shortDesc = """Low T polynomial Tmin changed from 300.0 to 298.0 K when importing to RMG.
C=CCC
Imported from MatheuCH4/Matheu_CH4_pyrolysis_gas_kinetics.inp.""",
    longDesc = 
"""
Formula: C4H8
Species name in model: C4H8
_auto-generated from kinetic-models database.
""",
)

entry(
    index = 3,
    label = "C4H9",
    molecule = 
"""
multiplicity 2
1  C u0 p0 c0 {2,S} {4,S} {5,S} {6,S}
2  C u0 p0 c0 {1,S} {7,S} {8,S} {9,S}
3  C u0 p0 c0 {4,S} {10,S} {11,S} {12,S}
4  C u1 p0 c0 {1,S} {3,S} {13,S}
5  H u0 p0 c0 {1,S}
6  H u0 p0 c0 {1,S}
7  H u0 p0 c0 {2,S}
8  H u0 p0 c0 {2,S}
9  H u0 p0 c0 {2,S}
10 H u0 p0 c0 {3,S}
11 H u0 p0 c0 {3,S}
12 H u0 p0 c0 {3,S}
13 H u0 p0 c0 {4,S}
""",
    thermo = NASA(
        polynomials = [
            NASAPolynomial(coeffs=[0.726539,0.0402442,-1.86072e-05,2.70873e-09,2.65031e-13,6205.91,23.8087], Tmin=(298,'K'), Tmax=(1380,'K')),
            NASAPolynomial(coeffs=[11.4414,0.0199003,-6.49021e-06,9.76023e-10,-5.53905e-14,2067.84,-35.3131], Tmin=(1380,'K'), Tmax=(5000,'K')),
        ],
        Tmin = (298,'K'),
        Tmax = (5000,'K'),
    ),
    shortDesc = """Low T polynomial Tmin changed from 300.0 to 298.0 K when importing to RMG.
C[CH]CC
Imported from MatheuCH4/Matheu_CH4_pyrolysis_gas_kinetics.inp.""",
    longDesc = 
"""
Formula: C4H9
Species name in model: C4H9
_auto-generated from kinetic-models database.
""",
)


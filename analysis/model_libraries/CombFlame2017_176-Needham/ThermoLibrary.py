#!/usr/bin/env python
# encoding: utf-8

name = "CombFlame2017/176-Needham"
shortDesc = "Thermo library for species appearing in shared reactions with Harris-Butane"
longDesc = """
Thermo entries from model CombFlame2017/176-Needham
filtered to species that participate in reactions shared with Harris-Butane.
Auto-generated from the kinetic-models database.
"""
entry(
    index = 0,
    label = "C2H2O",
    molecule = 
"""
1 O u0 p2 c0 {2,S} {5,S}
2 C u0 p0 c0 {1,S} {3,T}
3 C u0 p0 c0 {2,T} {4,S}
4 H u0 p0 c0 {3,S}
5 H u0 p0 c0 {1,S}
""",
    thermo = NASA(
        polynomials = [
            NASAPolynomial(coeffs=[1.24237,0.0310722,-5.08669e-05,4.31371e-08,-1.40146e-11,8031.61,13.8743], Tmin=(298,'K'), Tmax=(1000,'K')),
            NASAPolynomial(coeffs=[5.92383,0.00679236,-2.56586e-06,4.49878e-10,-2.99401e-14,7264.63,-7.60177], Tmin=(1000,'K'), Tmax=(5000,'K')),
        ],
        Tmin = (298,'K'),
        Tmax = (5000,'K'),
    ),
    shortDesc = """SRI91
_low T polynomial Tmin changed from 300.0 to 298.0 K when importing to RMG.
C#CO
_imported from CombFlame2017/176-Needham/YF_Thermo_Final.txt.""",
    longDesc = 
"""
Formula: C2H2O
Species name in model: HCCOH
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
            NASAPolynomial(coeffs=[3.40906,0.0107386,1.89149e-06,-7.15858e-09,2.86739e-12,62,9.57145], Tmin=(298,'K'), Tmax=(1000,'K')),
            NASAPolynomial(coeffs=[5.97567,0.00813059,-2.74362e-06,4.0703e-10,-2.17602e-14,-969.5,-5.03209], Tmin=(1000,'K'), Tmax=(5000,'K')),
        ],
        Tmin = (298,'K'),
        Tmax = (5000,'K'),
    ),
    shortDesc = """D05/83
_low T polynomial Tmin changed from 300.0 to 298.0 K when importing to RMG.
[CH2]C=O
_imported from CombFlame2017/176-Needham/YF_Thermo_Final.txt.""",
    longDesc = 
"""
Formula: C2H3O
Species name in model: CH2CHO
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
    shortDesc = """L 1/91.
C=C
_imported from CombFlame2017/176-Needham/YF_Thermo_Final.txt.""",
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
    shortDesc = """L12/92.
C[CH2]
_imported from CombFlame2017/176-Needham/YF_Thermo_Final.txt.""",
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
    shortDesc = """P11/94
_low T polynomial Tmin changed from 300.0 to 298.0 K when importing to RMG.
CC(C)C
_imported from CombFlame2017/176-Needham/YF_Thermo_Final.txt.""",
    longDesc = 
"""
Formula: C4H10
Species name in model: iC4H10
_auto-generated from kinetic-models database.
""",
)

entry(
    index = 5,
    label = "C4H8",
    molecule = 
"""
1  C u0 p0 c0 {3,S} {5,S} {6,S} {7,S}
2  C u0 p0 c0 {4,S} {8,S} {9,S} {10,S}
3  C u0 p0 c0 {1,S} {4,D} {11,S}
4  C u0 p0 c0 {2,S} {3,D} {12,S}
5  H u0 p0 c0 {1,S}
6  H u0 p0 c0 {1,S}
7  H u0 p0 c0 {1,S}
8  H u0 p0 c0 {2,S}
9  H u0 p0 c0 {2,S}
10 H u0 p0 c0 {2,S}
11 H u0 p0 c0 {3,S}
12 H u0 p0 c0 {4,S}
""",
    thermo = NASA(
        polynomials = [
            NASAPolynomial(coeffs=[1.25943,0.0278084,8.70139e-06,-2.44022e-08,9.89777e-12,-2964.77,20.5011], Tmin=(298,'K'), Tmax=(1000,'K')),
            NASAPolynomial(coeffs=[0.827977,0.0358645,-1.66345e-05,3.47328e-09,-2.66574e-13,-3052.1,21.3425], Tmin=(1000,'K'), Tmax=(5000,'K')),
        ],
        Tmin = (298,'K'),
        Tmax = (5000,'K'),
    ),
    shortDesc = """T 6/83
_low T polynomial Tmin changed from 300.0 to 298.0 K when importing to RMG.
CC=CC
_imported from CombFlame2017/176-Needham/YF_Thermo_Final.txt.""",
    longDesc = 
"""
Formula: C4H8
Species name in model: C4H82
_auto-generated from kinetic-models database.
""",
)

entry(
    index = 6,
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
    shortDesc = """P11/94
_low T polynomial Tmin changed from 300.0 to 298.0 K when importing to RMG.
C[C](C)C
_imported from CombFlame2017/176-Needham/YF_Thermo_Final.txt.""",
    longDesc = 
"""
Formula: C4H9
Species name in model: tC4H9
_auto-generated from kinetic-models database.
""",
)

entry(
    index = 7,
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
            NASAPolynomial(coeffs=[3.67359,0.00201095,5.73022e-06,-6.87117e-09,2.54386e-12,16445,1.60456], Tmin=(200,'K'), Tmax=(1000,'K')),
            NASAPolynomial(coeffs=[2.28572,0.0072399,-2.98714e-06,5.95685e-10,-4.67154e-14,16775.6,8.48007], Tmin=(1000,'K'), Tmax=(3500,'K')),
        ],
        Tmin = (200,'K'),
        Tmax = (3500,'K'),
    ),
    shortDesc = """L11/89.
[CH3]
_imported from CombFlame2017/176-Needham/YF_Thermo_Final.txt.""",
    longDesc = 
"""
Formula: CH3
Species name in model: CH3
_auto-generated from kinetic-models database.
""",
)

entry(
    index = 8,
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
            NASAPolynomial(coeffs=[5.14988,-0.013671,4.91801e-05,-4.84743e-08,1.66694e-11,-10246.6,-4.6413], Tmin=(200,'K'), Tmax=(1000,'K')),
            NASAPolynomial(coeffs=[0.0748515,0.0133909,-5.73286e-06,1.22293e-09,-1.01815e-13,-9468.34,18.4373], Tmin=(1000,'K'), Tmax=(3500,'K')),
        ],
        Tmin = (200,'K'),
        Tmax = (3500,'K'),
    ),
    shortDesc = """L 8/88.
C
_imported from CombFlame2017/176-Needham/YF_Thermo_Final.txt.""",
    longDesc = 
"""
Formula: CH4
Species name in model: CH4
_auto-generated from kinetic-models database.
""",
)

entry(
    index = 9,
    label = "H",
    molecule = 
"""
multiplicity 2
1 H u1 p0 c0
""",
    thermo = NASA(
        polynomials = [
            NASAPolynomial(coeffs=[2.5,7.05333e-13,-1.99592e-15,2.30082e-18,-9.27732e-22,25473.7,-0.446683], Tmin=(200,'K'), Tmax=(1000,'K')),
            NASAPolynomial(coeffs=[2.5,-2.30843e-11,1.61562e-14,-4.73515e-18,4.98197e-22,25473.7,-0.446683], Tmin=(1000,'K'), Tmax=(3500,'K')),
        ],
        Tmin = (200,'K'),
        Tmax = (3500,'K'),
    ),
    shortDesc = """L 7/88.
[H]
_imported from CombFlame2017/176-Needham/YF_Thermo_Final.txt.""",
    longDesc = 
"""
Formula: H
Species name in model: H
_auto-generated from kinetic-models database.
""",
)

entry(
    index = 10,
    label = "H2",
    molecule = 
"""
1 H u0 p0 c0 {2,S}
2 H u0 p0 c0 {1,S}
""",
    thermo = NASA(
        polynomials = [
            NASAPolynomial(coeffs=[2.34433,0.00798052,-1.94782e-05,2.01572e-08,-7.37612e-12,-917.935,0.68301], Tmin=(200,'K'), Tmax=(1000,'K')),
            NASAPolynomial(coeffs=[3.33728,-4.94025e-05,4.99457e-07,-1.79566e-10,2.00255e-14,-950.159,-3.20502], Tmin=(1000,'K'), Tmax=(3500,'K')),
        ],
        Tmin = (200,'K'),
        Tmax = (3500,'K'),
    ),
    shortDesc = """TPIS78.
[H][H]
_imported from CombFlame2017/176-Needham/YF_Thermo_Final.txt.""",
    longDesc = 
"""
Formula: H2
Species name in model: H2
_auto-generated from kinetic-models database.
""",
)

entry(
    index = 11,
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
            NASAPolynomial(coeffs=[4.27611,-0.000542822,1.67336e-05,-2.15771e-08,8.62454e-12,-17702.6,3.43505], Tmin=(200,'K'), Tmax=(1000,'K')),
            NASAPolynomial(coeffs=[4.165,0.00490832,-1.90139e-06,3.71186e-10,-2.87908e-14,-17861.8,2.91616], Tmin=(1000,'K'), Tmax=(3500,'K')),
        ],
        Tmin = (200,'K'),
        Tmax = (3500,'K'),
    ),
    shortDesc = """L 7/88.
OO
_imported from CombFlame2017/176-Needham/YF_Thermo_Final.txt.""",
    longDesc = 
"""
Formula: H2O2
Species name in model: H2O2
_auto-generated from kinetic-models database.
""",
)

entry(
    index = 12,
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
_imported from CombFlame2017/176-Needham/YF_Thermo_Final.txt.""",
    longDesc = 
"""
Formula: HO2
Species name in model: HO2
_auto-generated from kinetic-models database.
""",
)

entry(
    index = 13,
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
            NASAPolynomial(coeffs=[3.28254,0.00148309,-7.57967e-07,2.09471e-10,-2.16718e-14,-1088.46,5.45323], Tmin=(1000,'K'), Tmax=(3500,'K')),
        ],
        Tmin = (200,'K'),
        Tmax = (3500,'K'),
    ),
    shortDesc = """TPIS89.
[O][O]
_imported from CombFlame2017/176-Needham/YF_Thermo_Final.txt.""",
    longDesc = 
"""
Formula: O2
Species name in model: O2
_auto-generated from kinetic-models database.
""",
)


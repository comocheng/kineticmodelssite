#!/usr/bin/env python
# encoding: utf-8

name = "PCI2017/051-Pelucchi"
shortDesc = "Thermo library for species appearing in shared reactions with Harris-Butane"
longDesc = """
Thermo entries from model PCI2017/051-Pelucchi
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
            NASAPolynomial(coeffs=[2.97497,0.0121187,-2.34505e-06,-6.46668e-09,3.90565e-12,-7632.64,8.67355], Tmin=(298,'K'), Tmax=(1000,'K')),
            NASAPolynomial(coeffs=[6.03885,0.00580484,-1.92095e-06,2.79448e-10,-1.45887e-14,-8583.43,-7.65782], Tmin=(1000,'K'), Tmax=(4000,'K')),
        ],
        Tmin = (298,'K'),
        Tmax = (4000,'K'),
    ),
    shortDesc = """_low T polynomial Tmin changed from 300.0 to 298.0 K when importing to RMG.
C=C=O
_imported from PCI2017/051-Pelucchi/thermo.txt.""",
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
            NASAPolynomial(coeffs=[0.28022,0.0274031,-2.55468e-05,1.30668e-08,-2.75042e-12,668.265,22.3973], Tmin=(298,'K'), Tmax=(1500,'K')),
            NASAPolynomial(coeffs=[9.71006,0.00385497,-4.67782e-07,-1.50518e-10,2.94143e-14,-2692.48,-28.1056], Tmin=(1500,'K'), Tmax=(4000,'K')),
        ],
        Tmin = (298,'K'),
        Tmax = (4000,'K'),
    ),
    shortDesc = """_low T polynomial Tmin changed from 300.0 to 298.0 K when importing to RMG.
[CH2]C=O
_imported from PCI2017/051-Pelucchi/thermo.txt.""",
    longDesc = 
"""
Formula: C2H3O
Species name in model: CH2CHO
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
            NASAPolynomial(coeffs=[1.57642,0.0345897,6.97016e-06,-2.81636e-08,1.23751e-11,-17147,17.8727], Tmin=(298,'K'), Tmax=(1000,'K')),
            NASAPolynomial(coeffs=[10.5251,0.0235909,-7.85389e-06,1.14561e-09,-5.9931e-14,-20495.2,-32.1928], Tmin=(1000,'K'), Tmax=(4000,'K')),
        ],
        Tmin = (298,'K'),
        Tmax = (4000,'K'),
    ),
    shortDesc = """_low T polynomial Tmin changed from 300.0 to 298.0 K when importing to RMG.
CCCC
_imported from PCI2017/051-Pelucchi/thermo.txt.""",
    longDesc = 
"""
Formula: C4H10
Species name in model: NC4H10
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
            NASAPolynomial(coeffs=[1.18114,0.0308534,5.08652e-06,-2.46549e-08,1.11102e-11,-1790.4,21.0625], Tmin=(298,'K'), Tmax=(1000,'K')),
            NASAPolynomial(coeffs=[2.05358,0.0343505,-1.58832e-05,3.30897e-09,-2.5361e-13,-2139.72,15.5432], Tmin=(1000,'K'), Tmax=(4000,'K')),
        ],
        Tmin = (298,'K'),
        Tmax = (4000,'K'),
    ),
    shortDesc = """_low T polynomial Tmin changed from 300.0 to 298.0 K when importing to RMG.
C=CCC
_imported from PCI2017/051-Pelucchi/thermo.txt.""",
    longDesc = 
"""
Formula: C4H8
Species name in model: NC4H8
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
            NASAPolynomial(coeffs=[0.361027,0.0446561,-2.69622e-05,7.37513e-09,0,6794.88,25.2697], Tmin=(298,'K'), Tmax=(1000,'K')),
            NASAPolynomial(coeffs=[2.85927,0.0339093,-1.29635e-05,1.62487e-09,0,6441.32,13.6765], Tmin=(1000,'K'), Tmax=(4000,'K')),
        ],
        Tmin = (298,'K'),
        Tmax = (4000,'K'),
    ),
    shortDesc = """_low T polynomial Tmin changed from 300.0 to 298.0 K when importing to RMG.
[CH2]CCC
_imported from PCI2017/051-Pelucchi/thermo.txt.""",
    longDesc = 
"""
Formula: C4H9
Species name in model: NC4H9P
_auto-generated from kinetic-models database.
""",
)

entry(
    index = 5,
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
            NASAPolynomial(coeffs=[0.859226,0.0589774,-4.45935e-05,1.84502e-08,-3.2133e-12,-11959.9,25.4555], Tmin=(298,'K'), Tmax=(1392,'K')),
            NASAPolynomial(coeffs=[16.4199,0.0207668,-7.14062e-06,1.11233e-09,-6.46799e-14,-17290.9,-57.6445], Tmin=(1392,'K'), Tmax=(4000,'K')),
        ],
        Tmin = (298,'K'),
        Tmax = (4000,'K'),
    ),
    shortDesc = """_low T polynomial Tmin changed from 300.0 to 298.0 K when importing to RMG.
CCCCO[O]
_imported from PCI2017/051-Pelucchi/thermo.txt.""",
    longDesc = 
"""
Formula: C4H9O2
Species name in model: NC4H9-OO
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
            NASAPolynomial(coeffs=[2.43044,0.0111241,-1.68022e-05,1.62183e-08,-5.86495e-12,16423.8,6.78979], Tmin=(298,'K'), Tmax=(1000,'K')),
            NASAPolynomial(coeffs=[2.84406,0.00613797,-2.23034e-06,3.78516e-10,-2.45216e-14,16437.8,5.45266], Tmin=(1000,'K'), Tmax=(4000,'K')),
        ],
        Tmin = (298,'K'),
        Tmax = (4000,'K'),
    ),
    shortDesc = """_low T polynomial Tmin changed from 300.0 to 298.0 K when importing to RMG.
[CH3]
_imported from PCI2017/051-Pelucchi/thermo.txt.""",
    longDesc = 
"""
Formula: CH3
Species name in model: CH3
_auto-generated from kinetic-models database.
""",
)

entry(
    index = 7,
    label = "CH3O2",
    molecule = 
"""
multiplicity 2
1 O u0 p2 c0 {2,S} {3,S}
2 O u1 p2 c0 {1,S}
3 C u0 p0 c0 {1,S} {4,S} {5,S} {6,S}
4 H u0 p0 c0 {3,S}
5 H u0 p0 c0 {3,S}
6 H u0 p0 c0 {3,S}
""",
    thermo = NASA(
        polynomials = [
            NASAPolynomial(coeffs=[4.26147,0.0100874,-3.21506e-06,2.09409e-10,4.18339e-14,473.13,6.34599], Tmin=(298,'K'), Tmax=(1385,'K')),
            NASAPolynomial(coeffs=[5.95785,0.00790729,-2.68246e-06,4.13891e-10,-2.39007e-14,-378.179,-3.53671], Tmin=(1385,'K'), Tmax=(4000,'K')),
        ],
        Tmin = (298,'K'),
        Tmax = (4000,'K'),
    ),
    shortDesc = """_low T polynomial Tmin changed from 300.0 to 298.0 K when importing to RMG.
CO[O]
_imported from PCI2017/051-Pelucchi/thermo.txt.""",
    longDesc = 
"""
Formula: CH3O2
Species name in model: CH3OO
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
            NASAPolynomial(coeffs=[0.778742,0.0174767,-2.78341e-05,3.04971e-08,-1.22393e-11,-9825.23,13.7222], Tmin=(298,'K'), Tmax=(1000,'K')),
            NASAPolynomial(coeffs=[1.68347,0.0102372,-3.87513e-06,6.78558e-10,-4.50342e-14,-10080.8,9.62348], Tmin=(1000,'K'), Tmax=(4000,'K')),
        ],
        Tmin = (298,'K'),
        Tmax = (4000,'K'),
    ),
    shortDesc = """_low T polynomial Tmin changed from 300.0 to 298.0 K when importing to RMG.
C
_imported from PCI2017/051-Pelucchi/thermo.txt.""",
    longDesc = 
"""
Formula: CH4
Species name in model: CH4
_auto-generated from kinetic-models database.
""",
)

entry(
    index = 9,
    label = "CH4O2",
    molecule = 
"""
1 O u0 p2 c0 {2,S} {3,S}
2 O u0 p2 c0 {1,S} {7,S}
3 C u0 p0 c0 {1,S} {4,S} {5,S} {6,S}
4 H u0 p0 c0 {3,S}
5 H u0 p0 c0 {3,S}
6 H u0 p0 c0 {3,S}
7 H u0 p0 c0 {2,S}
""",
    thermo = NASA(
        polynomials = [
            NASAPolynomial(coeffs=[5.86865,0.0107942,-3.64553e-06,5.41291e-10,-2.89684e-14,-18126.9,-2.51762], Tmin=(298,'K'), Tmax=(1000,'K')),
            NASAPolynomial(coeffs=[5.63695,0.0111815,-3.69593e-06,4.0719e-10,0,-18044.3,-1.24167], Tmin=(1000,'K'), Tmax=(4000,'K')),
        ],
        Tmin = (298,'K'),
        Tmax = (4000,'K'),
    ),
    shortDesc = """_low T polynomial Tmin changed from 300.0 to 298.0 K when importing to RMG.
COO
_imported from PCI2017/051-Pelucchi/thermo.txt.""",
    longDesc = 
"""
Formula: CH4O2
Species name in model: CH3OOH
_auto-generated from kinetic-models database.
""",
)

entry(
    index = 10,
    label = "H",
    molecule = 
"""
multiplicity 2
1 H u1 p0 c0
""",
    thermo = NASA(
        polynomials = [
            NASAPolynomial(coeffs=[2.5,0,0,0,0,25471.6,-0.460118], Tmin=(298,'K'), Tmax=(1000,'K')),
            NASAPolynomial(coeffs=[2.5,0,0,0,0,25471.6,-0.460118], Tmin=(1000,'K'), Tmax=(4000,'K')),
        ],
        Tmin = (298,'K'),
        Tmax = (4000,'K'),
    ),
    shortDesc = """_low T polynomial Tmin changed from 300.0 to 298.0 K when importing to RMG.
[H]
_imported from PCI2017/051-Pelucchi/thermo.txt.""",
    longDesc = 
"""
Formula: H
Species name in model: H
_auto-generated from kinetic-models database.
""",
)

entry(
    index = 11,
    label = "H2",
    molecule = 
"""
1 H u0 p0 c0 {2,S}
2 H u0 p0 c0 {1,S}
""",
    thermo = NASA(
        polynomials = [
            NASAPolynomial(coeffs=[3.29812,0.000824944,-8.14301e-07,-9.47543e-11,4.13487e-13,-1012.52,-3.29409], Tmin=(298,'K'), Tmax=(1000,'K')),
            NASAPolynomial(coeffs=[2.99142,0.000700064,-5.63383e-08,-9.23158e-12,1.58275e-15,-835.034,-1.35511], Tmin=(1000,'K'), Tmax=(4000,'K')),
        ],
        Tmin = (298,'K'),
        Tmax = (4000,'K'),
    ),
    shortDesc = """_low T polynomial Tmin changed from 300.0 to 298.0 K when importing to RMG.
[H][H]
_imported from PCI2017/051-Pelucchi/thermo.txt.""",
    longDesc = 
"""
Formula: H2
Species name in model: H2
_auto-generated from kinetic-models database.
""",
)

entry(
    index = 12,
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
            NASAPolynomial(coeffs=[3.38875,0.00656923,-1.48501e-07,-4.62581e-09,2.47151e-12,-17663.1,6.78536], Tmin=(298,'K'), Tmax=(1000,'K')),
            NASAPolynomial(coeffs=[4.57317,0.00433614,-1.47469e-06,2.3489e-10,-1.43165e-14,-18007,0.501138], Tmin=(1000,'K'), Tmax=(4000,'K')),
        ],
        Tmin = (298,'K'),
        Tmax = (4000,'K'),
    ),
    shortDesc = """_low T polynomial Tmin changed from 300.0 to 298.0 K when importing to RMG.
OO
_imported from PCI2017/051-Pelucchi/thermo.txt.""",
    longDesc = 
"""
Formula: H2O2
Species name in model: H2O2
_auto-generated from kinetic-models database.
""",
)

entry(
    index = 13,
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
            NASAPolynomial(coeffs=[4.3018,-0.00474912,2.11583e-05,-2.42764e-08,9.29225e-12,294.808,3.71666], Tmin=(298,'K'), Tmax=(1000,'K')),
            NASAPolynomial(coeffs=[4.01721,0.00223982,-6.33658e-07,1.14246e-10,-1.07909e-14,111.857,3.7851], Tmin=(1000,'K'), Tmax=(4000,'K')),
        ],
        Tmin = (298,'K'),
        Tmax = (4000,'K'),
    ),
    shortDesc = """_low T polynomial Tmin changed from 300.0 to 298.0 K when importing to RMG.
[O]O
_imported from PCI2017/051-Pelucchi/thermo.txt.""",
    longDesc = 
"""
Formula: HO2
Species name in model: HO2
_auto-generated from kinetic-models database.
""",
)

entry(
    index = 14,
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
            NASAPolynomial(coeffs=[3.69758,0.00061352,-1.25884e-07,1.77528e-11,-1.13644e-15,-1233.93,3.18917], Tmin=(1000,'K'), Tmax=(4000,'K')),
        ],
        Tmin = (298,'K'),
        Tmax = (4000,'K'),
    ),
    shortDesc = """_low T polynomial Tmin changed from 300.0 to 298.0 K when importing to RMG.
[O][O]
_imported from PCI2017/051-Pelucchi/thermo.txt.""",
    longDesc = 
"""
Formula: O2
Species name in model: O2
_auto-generated from kinetic-models database.
""",
)


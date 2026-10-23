#!/usr/bin/env python
# encoding: utf-8

name = "PCI2013/297-Herbinet"
shortDesc = "Thermo library for species appearing in shared reactions with Harris-Butane"
longDesc = """
Thermo entries from model PCI2013/297-Herbinet
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
            NASAPolynomial(coeffs=[2.99539,0.012354,-4.06499e-06,-3.34608e-09,2.24152e-12,-7150.97,8.53716], Tmin=(298,'K'), Tmax=(1000,'K')),
            NASAPolynomial(coeffs=[5.35267,0.00694209,-2.50061e-06,4.13231e-10,-2.59692e-14,-7810.07,-3.80283], Tmin=(1000,'K'), Tmax=(5000,'K')),
        ],
        Tmin = (298,'K'),
        Tmax = (5000,'K'),
    ),
    shortDesc = """_low T polynomial Tmin changed from 300.0 to 298.0 K when importing to RMG.
C=C=O
_imported from PCI2013/297-Herbinet/mechanism.txt.""",
    longDesc = 
"""
Formula: C2H2O
Species name in model: CH2COZ
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
            NASAPolynomial(coeffs=[2.79503,0.0101099,1.61751e-05,-3.10303e-08,1.39436e-11,162.945,12.3647], Tmin=(200,'K'), Tmax=(1000,'K')),
            NASAPolynomial(coeffs=[6.53928,0.00780239,-2.76414e-06,4.42099e-10,-2.62954e-14,-1188.59,-8.72091], Tmin=(1000,'K'), Tmax=(6000,'K')),
        ],
        Tmin = (200,'K'),
        Tmax = (6000,'K'),
    ),
    shortDesc = """MF-BURCAT.
[CH2]C=O
_imported from PCI2013/297-Herbinet/mechanism.txt.""",
    longDesc = 
"""
Formula: C2H3O
Species name in model: R13CH2CHO
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
            NASAPolynomial(coeffs=[1.3181,0.014446,-2.74335e-06,-3.10835e-09,1.52772e-12,5268.17,14.7233], Tmin=(298,'K'), Tmax=(1000,'K')),
            NASAPolynomial(coeffs=[0.39972,0.0167299,-6.80909e-06,1.22922e-09,-8.23928e-14,5637.49,19.7729], Tmin=(1000,'K'), Tmax=(5000,'K')),
        ],
        Tmin = (298,'K'),
        Tmax = (5000,'K'),
    ),
    shortDesc = """_low T polynomial Tmin changed from 300.0 to 298.0 K when importing to RMG.
C=C
_imported from PCI2013/297-Herbinet/mechanism.txt.""",
    longDesc = 
"""
Formula: C2H4
Species name in model: C2H4Z
_auto-generated from kinetic-models database.
""",
)

entry(
    index = 3,
    label = "C2H4O",
    molecule = 
"""
1 O u0 p2 c0 {3,D}
2 C u0 p0 c0 {3,S} {4,S} {5,S} {6,S}
3 C u0 p0 c0 {1,D} {2,S} {7,S}
4 H u0 p0 c0 {2,S}
5 H u0 p0 c0 {2,S}
6 H u0 p0 c0 {2,S}
7 H u0 p0 c0 {3,S}
""",
    thermo = NASA(
        polynomials = [
            NASAPolynomial(coeffs=[2.76016,0.0118896,6.7576e-06,-1.19653e-08,4.15644e-12,-21409.8,12.2635], Tmin=(298,'K'), Tmax=(1000,'K')),
            NASAPolynomial(coeffs=[4.32357,0.0133651,-4.84704e-06,8.08214e-10,-5.12972e-14,-22194.6,2.58472], Tmin=(1000,'K'), Tmax=(5000,'K')),
        ],
        Tmin = (298,'K'),
        Tmax = (5000,'K'),
    ),
    shortDesc = """_low T polynomial Tmin changed from 300.0 to 298.0 K when importing to RMG.
CC=O
_imported from PCI2013/297-Herbinet/mechanism.txt.""",
    longDesc = 
"""
Formula: C2H4O
Species name in model: CH3CHO
_auto-generated from kinetic-models database.
""",
)

entry(
    index = 4,
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
            NASAPolynomial(coeffs=[0.54658,0.0204368,-1.16694e-05,4.82541e-09,-1.19281e-12,13274.3,20.9001], Tmin=(298,'K'), Tmax=(1000,'K')),
            NASAPolynomial(coeffs=[3.50261,0.0126143,-3.6573e-06,5.16642e-10,-2.90469e-14,12403.2,5.44236], Tmin=(1000,'K'), Tmax=(5000,'K')),
        ],
        Tmin = (298,'K'),
        Tmax = (5000,'K'),
    ),
    shortDesc = """_low T polynomial Tmin changed from 300.0 to 298.0 K when importing to RMG.
C[CH2]
_imported from PCI2013/297-Herbinet/mechanism.txt.""",
    longDesc = 
"""
Formula: C2H5
Species name in model: R11C2H5
_auto-generated from kinetic-models database.
""",
)

entry(
    index = 5,
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
            NASAPolynomial(coeffs=[0.0599796,0.0440056,-1.55321e-05,-5.28063e-09,4.04421e-12,-17040,24.5658], Tmin=(298,'K'), Tmax=(1000,'K')),
            NASAPolynomial(coeffs=[7.71333,0.0277676,-9.61563e-06,1.54561e-09,-9.52813e-14,-19425.2,-16.2625], Tmin=(1000,'K'), Tmax=(5000,'K')),
        ],
        Tmin = (298,'K'),
        Tmax = (5000,'K'),
    ),
    shortDesc = """0
_low T polynomial Tmin changed from 300.0 to 298.0 K when importing to RMG.
CCCC
_imported from PCI2013/297-Herbinet/mechanism.txt.""",
    longDesc = 
"""
Formula: C4H10
Species name in model: C4H10
_auto-generated from kinetic-models database.
""",
)

entry(
    index = 6,
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
            NASAPolynomial(coeffs=[-0.258697,0.0414755,-2.13177e-05,2.79188e-09,8.57493e-13,-1618.1,26.7207], Tmin=(298,'K'), Tmax=(1000,'K')),
            NASAPolynomial(coeffs=[9.30019,0.0198715,-6.5714e-06,1.02589e-09,-6.21604e-14,-4664.97,-24.2603], Tmin=(1000,'K'), Tmax=(5000,'K')),
        ],
        Tmin = (298,'K'),
        Tmax = (5000,'K'),
    ),
    shortDesc = """0
_low T polynomial Tmin changed from 300.0 to 298.0 K when importing to RMG.
C=CCC
_imported from PCI2013/297-Herbinet/mechanism.txt.""",
    longDesc = 
"""
Formula: C4H8
Species name in model: C4H8Y
_auto-generated from kinetic-models database.
""",
)

entry(
    index = 7,
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
            NASAPolynomial(coeffs=[0.126099,0.0472341,-3.31243e-05,1.27128e-08,-1.71295e-12,6373.08,25.665], Tmin=(298,'K'), Tmax=(1000,'K')),
            NASAPolynomial(coeffs=[7.4632,0.0242658,-7.60323e-06,1.14631e-09,-6.80177e-14,4575.73,-11.3659], Tmin=(1000,'K'), Tmax=(5000,'K')),
        ],
        Tmin = (298,'K'),
        Tmax = (5000,'K'),
    ),
    shortDesc = """_low T polynomial Tmin changed from 300.0 to 298.0 K when importing to RMG.
C[CH]CC
_imported from PCI2013/297-Herbinet/mechanism.txt.""",
    longDesc = 
"""
Formula: C4H9
Species name in model: R326C4H9
_auto-generated from kinetic-models database.
""",
)

entry(
    index = 8,
    label = "C4H9O2",
    molecule = 
"""
multiplicity 2
1  O u0 p2 c0 {2,S} {4,S}
2  O u0 p2 c0 {1,S} {15,S}
3  C u0 p0 c0 {5,S} {6,S} {7,S} {8,S}
4  C u0 p0 c0 {1,S} {6,S} {12,S} {13,S}
5  C u0 p0 c0 {3,S} {9,S} {10,S} {11,S}
6  C u1 p0 c0 {3,S} {4,S} {14,S}
7  H u0 p0 c0 {3,S}
8  H u0 p0 c0 {3,S}
9  H u0 p0 c0 {5,S}
10 H u0 p0 c0 {5,S}
11 H u0 p0 c0 {5,S}
12 H u0 p0 c0 {4,S}
13 H u0 p0 c0 {4,S}
14 H u0 p0 c0 {6,S}
15 H u0 p0 c0 {2,S}
""",
    thermo = NASA(
        polynomials = [
            NASAPolynomial(coeffs=[0.417461,0.0669291,-6.64108e-05,3.82301e-08,-9.33502e-12,-4430.46,29.7172], Tmin=(298,'K'), Tmax=(1000,'K')),
            NASAPolynomial(coeffs=[16.0515,0.0178643,-4.69452e-06,6.23121e-10,-3.38685e-14,-8562.66,-49.8618], Tmin=(1000,'K'), Tmax=(5000,'K')),
        ],
        Tmin = (298,'K'),
        Tmax = (5000,'K'),
    ),
    shortDesc = """_low T polynomial Tmin changed from 300.0 to 298.0 K when importing to RMG.
CC[CH]COO
_imported from PCI2013/297-Herbinet/mechanism.txt.""",
    longDesc = 
"""
Formula: C4H9O2
Species name in model: R44C4H9O2P
_auto-generated from kinetic-models database.
""",
)

entry(
    index = 9,
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
            NASAPolynomial(coeffs=[2.94974,0.0051194,-8.75334e-07,6.64224e-10,-5.42393e-13,16148.6,5.05087], Tmin=(298,'K'), Tmax=(1000,'K')),
            NASAPolynomial(coeffs=[1.02702,0.00949641,-3.8286e-06,6.86498e-10,-4.579e-14,16762.4,15.3006], Tmin=(1000,'K'), Tmax=(5000,'K')),
        ],
        Tmin = (298,'K'),
        Tmax = (5000,'K'),
    ),
    shortDesc = """_low T polynomial Tmin changed from 300.0 to 298.0 K when importing to RMG.
[CH3]
_imported from PCI2013/297-Herbinet/mechanism.txt.""",
    longDesc = 
"""
Formula: CH3
Species name in model: R4CH3
_auto-generated from kinetic-models database.
""",
)

entry(
    index = 10,
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
            NASAPolynomial(coeffs=[2.31954,0.00654738,-7.48051e-07,2.60912e-09,-1.95537e-12,-9997.64,7.24965], Tmin=(298,'K'), Tmax=(1000,'K')),
            NASAPolynomial(coeffs=[1.61991,0.010308,-3.71228e-06,6.14185e-10,-3.86748e-14,-10074.8,9.98982], Tmin=(1000,'K'), Tmax=(5000,'K')),
        ],
        Tmin = (298,'K'),
        Tmax = (5000,'K'),
    ),
    shortDesc = """_low T polynomial Tmin changed from 300.0 to 298.0 K when importing to RMG.
C
_imported from PCI2013/297-Herbinet/mechanism.txt.""",
    longDesc = 
"""
Formula: CH4
Species name in model: CH4
_auto-generated from kinetic-models database.
""",
)

entry(
    index = 11,
    label = "H",
    molecule = 
"""
multiplicity 2
1 H u1 p0 c0
""",
    thermo = NASA(
        polynomials = [
            NASAPolynomial(coeffs=[2.51984,-2.5992e-05,6.27898e-08,-6.29951e-11,2.23973e-14,25464.1,-0.563259], Tmin=(298,'K'), Tmax=(1000,'K')),
            NASAPolynomial(coeffs=[2.51382,4.09189e-06,-2.41082e-09,5.71874e-13,-4.70917e-17,25465.4,-0.534746], Tmin=(1000,'K'), Tmax=(5000,'K')),
        ],
        Tmin = (298,'K'),
        Tmax = (5000,'K'),
    ),
    shortDesc = """_low T polynomial Tmin changed from 300.0 to 298.0 K when importing to RMG.
[H]
_imported from PCI2013/297-Herbinet/mechanism.txt.""",
    longDesc = 
"""
Formula: H
Species name in model: R1H
_auto-generated from kinetic-models database.
""",
)

entry(
    index = 12,
    label = "H2",
    molecule = 
"""
1 H u0 p0 c0 {2,S}
2 H u0 p0 c0 {1,S}
""",
    thermo = NASA(
        polynomials = [
            NASAPolynomial(coeffs=[3.43853,0.000144314,-1.08191e-07,2.16839e-10,-5.54307e-14,-1037.49,-3.92682], Tmin=(298,'K'), Tmax=(1000,'K')),
            NASAPolynomial(coeffs=[2.5017,0.00178083,-7.80013e-07,1.48437e-10,-1.03401e-14,-686.891,1.25553], Tmin=(1000,'K'), Tmax=(5000,'K')),
        ],
        Tmin = (298,'K'),
        Tmax = (5000,'K'),
    ),
    shortDesc = """_low T polynomial Tmin changed from 300.0 to 298.0 K when importing to RMG.
[H][H]
_imported from PCI2013/297-Herbinet/mechanism.txt.""",
    longDesc = 
"""
Formula: H2
Species name in model: H2
_auto-generated from kinetic-models database.
""",
)

entry(
    index = 13,
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
            NASAPolynomial(coeffs=[2.79724,0.00930806,-3.27081e-06,-3.91853e-09,2.63341e-12,-17595.1,9.47142], Tmin=(298,'K'), Tmax=(1000,'K')),
            NASAPolynomial(coeffs=[5.20269,0.0030782,-8.47786e-07,1.14867e-10,-6.24436e-15,-18173.7,-2.81106], Tmin=(1000,'K'), Tmax=(5000,'K')),
        ],
        Tmin = (298,'K'),
        Tmax = (5000,'K'),
    ),
    shortDesc = """_low T polynomial Tmin changed from 300.0 to 298.0 K when importing to RMG.
OO
_imported from PCI2013/297-Herbinet/mechanism.txt.""",
    longDesc = 
"""
Formula: H2O2
Species name in model: H2O2
_auto-generated from kinetic-models database.
""",
)

entry(
    index = 14,
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
            NASAPolynomial(coeffs=[1.46289,0.0137444,-1.63684e-05,9.09343e-09,-1.98181e-12,811.955,15.0488], Tmin=(298,'K'), Tmax=(1000,'K')),
            NASAPolynomial(coeffs=[5.19598,0.000817576,-6.85172e-08,3.5108e-12,-9.27239e-17,-14.8555,-3.42694], Tmin=(1000,'K'), Tmax=(5000,'K')),
        ],
        Tmin = (298,'K'),
        Tmax = (5000,'K'),
    ),
    shortDesc = """_low T polynomial Tmin changed from 300.0 to 298.0 K when importing to RMG.
[O]O
_imported from PCI2013/297-Herbinet/mechanism.txt.""",
    longDesc = 
"""
Formula: HO2
Species name in model: R3OOH
_auto-generated from kinetic-models database.
""",
)

entry(
    index = 15,
    label = "O2",
    molecule = 
"""
multiplicity 3
1 O u1 p2 c0 {2,S}
2 O u1 p2 c0 {1,S}
""",
    thermo = NASA(
        polynomials = [
            NASAPolynomial(coeffs=[3.08809,0.00160342,-5.3455e-07,2.80793e-11,2.98899e-15,-993.828,6.61069], Tmin=(298,'K'), Tmax=(1000,'K')),
            NASAPolynomial(coeffs=[3.19345,0.00156657,-6.90657e-07,1.32082e-10,-9.23577e-15,-1052.28,5.96618], Tmin=(1000,'K'), Tmax=(5000,'K')),
        ],
        Tmin = (298,'K'),
        Tmax = (5000,'K'),
    ),
    shortDesc = """_low T polynomial Tmin changed from 300.0 to 298.0 K when importing to RMG.
[O][O]
_imported from PCI2013/297-Herbinet/mechanism.txt.""",
    longDesc = 
"""
Formula: O2
Species name in model: O2
_auto-generated from kinetic-models database.
""",
)


#!/usr/bin/env python
# encoding: utf-8

name = "PCI2017/047-Rodriguez"
shortDesc = "Thermo library for species appearing in shared reactions with Harris-Butane"
longDesc = """
Thermo entries from model PCI2017/047-Rodriguez
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
            NASAPolynomial(coeffs=[5.3511,0.00694209,-2.50061e-06,4.13231e-10,-2.59692e-14,-7808.51,-3.79201], Tmin=(1000,'K'), Tmax=(5000,'K')),
        ],
        Tmin = (298,'K'),
        Tmax = (5000,'K'),
    ),
    shortDesc = """_low T polynomial Tmin changed from 300.0 to 298.0 K when importing to RMG.
C=C=O
_imported from PCI2017/047-Rodriguez/mechanism.txt.""",
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
2 C u0 p0 c0 {3,S} {4,S} {5,S} {6,S}
3 C u1 p0 c0 {1,D} {2,S}
4 H u0 p0 c0 {2,S}
5 H u0 p0 c0 {2,S}
6 H u0 p0 c0 {2,S}
""",
    thermo = NASA(
        polynomials = [
            NASAPolynomial(coeffs=[3.85793,0.00540231,9.49967e-06,-9.349e-09,2.06672e-12,-2671.19,8.54331], Tmin=(298,'K'), Tmax=(1000,'K')),
            NASAPolynomial(coeffs=[10.9495,0.000544143,-1.58659e-08,-2.31074e-13,4.62528e-17,-6085.73,-33.4274], Tmin=(1000,'K'), Tmax=(5000,'K')),
        ],
        Tmin = (298,'K'),
        Tmax = (5000,'K'),
    ),
    shortDesc = """_low T polynomial Tmin changed from 300.0 to 298.0 K when importing to RMG.
C[C]=O
_imported from PCI2017/047-Rodriguez/mechanism.txt.""",
    longDesc = 
"""
Formula: C2H3O
Species name in model: R14CH3CO
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
            NASAPolynomial(coeffs=[1.3181,0.014446,-2.74335e-06,-3.10835e-09,1.52772e-12,5268.17,14.7233], Tmin=(298,'K'), Tmax=(1090,'K')),
            NASAPolynomial(coeffs=[0.314681,0.0167299,-6.80909e-06,1.22922e-09,-8.23928e-14,5724.99,20.3627], Tmin=(1090,'K'), Tmax=(5000,'K')),
        ],
        Tmin = (298,'K'),
        Tmax = (5000,'K'),
    ),
    shortDesc = """_low T polynomial Tmin changed from 300.0 to 298.0 K when importing to RMG.
C=C
_imported from PCI2017/047-Rodriguez/mechanism.txt.""",
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
            NASAPolynomial(coeffs=[2.69691,0.0123343,5.67465e-06,-1.08707e-08,3.76482e-12,-21403.1,12.5305], Tmin=(298,'K'), Tmax=(1000,'K')),
            NASAPolynomial(coeffs=[4.25981,0.013486,-4.91834e-06,8.2515e-10,-5.26943e-14,-22171.4,2.93484], Tmin=(1000,'K'), Tmax=(5000,'K')),
        ],
        Tmin = (298,'K'),
        Tmax = (5000,'K'),
    ),
    shortDesc = """_low T polynomial Tmin changed from 300.0 to 298.0 K when importing to RMG.
CC=O
_imported from PCI2017/047-Rodriguez/mechanism.txt.""",
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
            NASAPolynomial(coeffs=[3.50198,0.0126143,-3.6573e-06,5.16642e-10,-2.90469e-14,12403.9,5.44665], Tmin=(1000,'K'), Tmax=(5000,'K')),
        ],
        Tmin = (298,'K'),
        Tmax = (5000,'K'),
    ),
    shortDesc = """_low T polynomial Tmin changed from 300.0 to 298.0 K when importing to RMG.
C[CH2]
_imported from PCI2017/047-Rodriguez/mechanism.txt.""",
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
            NASAPolynomial(coeffs=[7.69471,0.0277676,-9.61563e-06,1.54561e-09,-9.52813e-14,-19406.6,-16.1338], Tmin=(1000,'K'), Tmax=(5000,'K')),
        ],
        Tmin = (298,'K'),
        Tmax = (5000,'K'),
    ),
    shortDesc = """0
_low T polynomial Tmin changed from 300.0 to 298.0 K when importing to RMG.
CCCC
_imported from PCI2017/047-Rodriguez/mechanism.txt.""",
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
            NASAPolynomial(coeffs=[9.2847,0.0198715,-6.5714e-06,1.02589e-09,-6.21604e-14,-4649.47,-24.1532], Tmin=(1000,'K'), Tmax=(5000,'K')),
        ],
        Tmin = (298,'K'),
        Tmax = (5000,'K'),
    ),
    shortDesc = """0
_low T polynomial Tmin changed from 300.0 to 298.0 K when importing to RMG.
C=CCC
_imported from PCI2017/047-Rodriguez/mechanism.txt.""",
    longDesc = 
"""
Formula: C4H8
Species name in model: nC4H8Y
_auto-generated from kinetic-models database.
""",
)

entry(
    index = 7,
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
            NASAPolynomial(coeffs=[-0.506119,0.0507221,-3.74398e-05,1.45966e-08,-1.90079e-12,7195.71,28.3231], Tmin=(298,'K'), Tmax=(1000,'K')),
            NASAPolynomial(coeffs=[7.05282,0.0253221,-8.04531e-06,1.21383e-09,-7.14512e-14,5518.43,-9.18587], Tmin=(1000,'K'), Tmax=(5000,'K')),
        ],
        Tmin = (298,'K'),
        Tmax = (5000,'K'),
    ),
    shortDesc = """_low T polynomial Tmin changed from 300.0 to 298.0 K when importing to RMG.
[CH2]CCC
_imported from PCI2017/047-Rodriguez/mechanism.txt.""",
    longDesc = 
"""
Formula: C4H9
Species name in model: R20C4H9
_auto-generated from kinetic-models database.
""",
)

entry(
    index = 8,
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
            NASAPolynomial(coeffs=[3.02665,0.00453516,6.85353e-07,-1.08392e-09,1.54976e-13,16144.4,4.70425], Tmin=(298,'K'), Tmax=(1022,'K')),
            NASAPolynomial(coeffs=[2.97239,0.00623239,-2.21904e-06,3.65778e-10,-2.30591e-14,15991.3,4.39516], Tmin=(1022,'K'), Tmax=(5000,'K')),
        ],
        Tmin = (298,'K'),
        Tmax = (5000,'K'),
    ),
    shortDesc = """_low T polynomial Tmin changed from 300.0 to 298.0 K when importing to RMG.
[CH3]
_imported from PCI2017/047-Rodriguez/mechanism.txt.""",
    longDesc = 
"""
Formula: CH3
Species name in model: R4CH3
_auto-generated from kinetic-models database.
""",
)

entry(
    index = 9,
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
            NASAPolynomial(coeffs=[2.31954,0.00654738,-7.48051e-07,2.60912e-09,-1.95537e-12,-9997.64,7.24965], Tmin=(298,'K'), Tmax=(1015,'K')),
            NASAPolynomial(coeffs=[1.60808,0.010308,-3.71228e-06,6.14185e-10,-3.86748e-14,-10063.1,10.0715], Tmin=(1015,'K'), Tmax=(5000,'K')),
        ],
        Tmin = (298,'K'),
        Tmax = (5000,'K'),
    ),
    shortDesc = """_low T polynomial Tmin changed from 300.0 to 298.0 K when importing to RMG.
C
_imported from PCI2017/047-Rodriguez/mechanism.txt.""",
    longDesc = 
"""
Formula: CH4
Species name in model: CH4
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
            NASAPolynomial(coeffs=[2.51984,-2.5992e-05,6.27898e-08,-6.29951e-11,2.23973e-14,25464.1,-0.563259], Tmin=(298,'K'), Tmax=(1000,'K')),
            NASAPolynomial(coeffs=[2.51383,4.09189e-06,-2.41082e-09,5.71874e-13,-4.70917e-17,25465.4,-0.534834], Tmin=(1000,'K'), Tmax=(5000,'K')),
        ],
        Tmin = (298,'K'),
        Tmax = (5000,'K'),
    ),
    shortDesc = """_low T polynomial Tmin changed from 300.0 to 298.0 K when importing to RMG.
[H]
_imported from PCI2017/047-Rodriguez/mechanism.txt.""",
    longDesc = 
"""
Formula: H
Species name in model: R1H
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
            NASAPolynomial(coeffs=[3.43853,0.000144314,-1.08191e-07,2.16839e-10,-5.54307e-14,-1037.49,-3.92682], Tmin=(298,'K'), Tmax=(1000,'K')),
            NASAPolynomial(coeffs=[2.49715,0.00178083,-7.80013e-07,1.48437e-10,-1.03401e-14,-682.342,1.28694], Tmin=(1000,'K'), Tmax=(5000,'K')),
        ],
        Tmin = (298,'K'),
        Tmax = (5000,'K'),
    ),
    shortDesc = """_low T polynomial Tmin changed from 300.0 to 298.0 K when importing to RMG.
[H][H]
_imported from PCI2017/047-Rodriguez/mechanism.txt.""",
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
            NASAPolynomial(coeffs=[2.52652,0.0113918,-8.90373e-06,2.45312e-09,7.18612e-14,-17565.3,10.5595], Tmin=(298,'K'), Tmax=(1014,'K')),
            NASAPolynomial(coeffs=[5.4774,0.00266518,-6.93806e-07,9.13913e-11,-4.93746e-15,-18283.7,-4.39626], Tmin=(1014,'K'), Tmax=(5000,'K')),
        ],
        Tmin = (298,'K'),
        Tmax = (5000,'K'),
    ),
    shortDesc = """_low T polynomial Tmin changed from 300.0 to 298.0 K when importing to RMG.
OO
_imported from PCI2017/047-Rodriguez/mechanism.txt.""",
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
            NASAPolynomial(coeffs=[1.84854,0.0107988,-8.54635e-06,4.18415e-10,1.44074e-12,326.446,13.4319], Tmin=(298,'K'), Tmax=(1000,'K')),
            NASAPolynomial(coeffs=[4.73204,0.00138622,-1.68457e-07,1.05843e-11,-2.40717e-16,-253.24,-0.766779], Tmin=(1000,'K'), Tmax=(5000,'K')),
        ],
        Tmin = (298,'K'),
        Tmax = (5000,'K'),
    ),
    shortDesc = """_low T polynomial Tmin changed from 300.0 to 298.0 K when importing to RMG.
[O]O
_imported from PCI2017/047-Rodriguez/mechanism.txt.""",
    longDesc = 
"""
Formula: HO2
Species name in model: R3OOH
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
            NASAPolynomial(coeffs=[3.08809,0.00160342,-5.3455e-07,2.80793e-11,2.98899e-15,-993.828,6.61069], Tmin=(298,'K'), Tmax=(1000,'K')),
            NASAPolynomial(coeffs=[3.18927,0.00156657,-6.90657e-07,1.32082e-10,-9.23577e-15,-1048.1,5.99506], Tmin=(1000,'K'), Tmax=(5000,'K')),
        ],
        Tmin = (298,'K'),
        Tmax = (5000,'K'),
    ),
    shortDesc = """_low T polynomial Tmin changed from 300.0 to 298.0 K when importing to RMG.
[O][O]
_imported from PCI2017/047-Rodriguez/mechanism.txt.""",
    longDesc = 
"""
Formula: O2
Species name in model: O2
_auto-generated from kinetic-models database.
""",
)


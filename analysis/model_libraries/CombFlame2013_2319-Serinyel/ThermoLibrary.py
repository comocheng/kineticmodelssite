#!/usr/bin/env python
# encoding: utf-8

name = "CombFlame2013/2319-Serinyel"
shortDesc = "Thermo library for species appearing in shared reactions with Harris-Butane"
longDesc = """
Thermo entries from model CombFlame2013/2319-Serinyel
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
            NASAPolynomial(coeffs=[1.3181,0.014446,-2.74335e-06,-3.10835e-09,1.52772e-12,5268.17,14.7233], Tmin=(298,'K'), Tmax=(1090,'K')),
            NASAPolynomial(coeffs=[0.314681,0.0167299,-6.80909e-06,1.22922e-09,-8.23928e-14,5724.99,20.3627], Tmin=(1090,'K'), Tmax=(5000,'K')),
        ],
        Tmin = (298,'K'),
        Tmax = (5000,'K'),
    ),
    shortDesc = """Low T polynomial Tmin changed from 300.0 to 298.0 K when importing to RMG.
C=C
Imported from CombFlame2013/2319-Serinyel/thermo.txt.""",
    longDesc = 
"""
Formula: C2H4
Species name in model: C2H4Z
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
            NASAPolynomial(coeffs=[0.54658,0.0204368,-1.16694e-05,4.82541e-09,-1.19281e-12,13274.3,20.9001], Tmin=(298,'K'), Tmax=(1000,'K')),
            NASAPolynomial(coeffs=[3.50261,0.0126143,-3.6573e-06,5.16642e-10,-2.90469e-14,12403.2,5.44236], Tmin=(1000,'K'), Tmax=(5000,'K')),
        ],
        Tmin = (298,'K'),
        Tmax = (5000,'K'),
    ),
    shortDesc = """Low T polynomial Tmin changed from 300.0 to 298.0 K when importing to RMG.
C[CH2]
Imported from CombFlame2013/2319-Serinyel/thermo.txt.""",
    longDesc = 
"""
Formula: C2H5
Species name in model: R11C2H5
_auto-generated from kinetic-models database.
""",
)

entry(
    index = 2,
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
    shortDesc = """Low T polynomial Tmin changed from 300.0 to 298.0 K when importing to RMG.
OO
Imported from CombFlame2013/2319-Serinyel/thermo.txt.""",
    longDesc = 
"""
Formula: H2O2
Species name in model: H2O2
_auto-generated from kinetic-models database.
""",
)

entry(
    index = 3,
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
            NASAPolynomial(coeffs=[4.72022,0.00138622,-1.68457e-07,1.05843e-11,-2.40717e-16,-241.43,-0.685165], Tmin=(1000,'K'), Tmax=(5000,'K')),
        ],
        Tmin = (298,'K'),
        Tmax = (5000,'K'),
    ),
    shortDesc = """Low T polynomial Tmin changed from 300.0 to 298.0 K when importing to RMG.
[O]O
Imported from CombFlame2013/2319-Serinyel/thermo.txt.""",
    longDesc = 
"""
Formula: HO2
Species name in model: R3OOH
_auto-generated from kinetic-models database.
""",
)


#!/usr/bin/env python
# encoding: utf-8

name = "CombFlame2014/711-Allen"
shortDesc = "Thermo library for species appearing in shared reactions with Harris-Butane"
longDesc = """
Thermo entries from model CombFlame2014/711-Allen
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
            NASAPolynomial(coeffs=[3.87057,-0.00652548,4.84652e-05,-5.25238e-08,1.79236e-11,5081.35,4.4624], Tmin=(250,'K'), Tmax=(995.04,'K')),
            NASAPolynomial(coeffs=[4.45388,0.00940071,-3.08614e-06,4.68495e-10,-2.68872e-14,4060.75,-2.89394], Tmin=(995.04,'K'), Tmax=(5000,'K')),
        ],
        Tmin = (250,'K'),
        Tmax = (5000,'K'),
    ),
    shortDesc = """Primary Thermo Library: DFT_QCI_thermo (Species ID: C2H4).
C=C
Imported from CombFlame2014/711-Allen/thermo.txt.""",
    longDesc = 
"""
Formula: C2H4
Species name in model: C2H4(50)
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
            NASAPolynomial(coeffs=[3.87194,-0.000357532,3.69681e-05,-4.21755e-08,1.4589e-11,13171.5,6.49793], Tmin=(250,'K'), Tmax=(995.04,'K')),
            NASAPolynomial(coeffs=[4.74777,0.0114086,-3.81375e-06,5.87463e-10,-3.41129e-14,12240.4,-1.5259], Tmin=(995.04,'K'), Tmax=(5000,'K')),
        ],
        Tmin = (250,'K'),
        Tmax = (5000,'K'),
    ),
    shortDesc = """Primary Thermo Library: DFT_QCI_thermo (Species ID: C2H5).
C[CH2]
Imported from CombFlame2014/711-Allen/thermo.txt.""",
    longDesc = 
"""
Formula: C2H5
Species name in model: C2H5(66)
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
            NASAPolynomial(coeffs=[3.87982,0.00267032,8.60206e-06,-1.18723e-08,4.39483e-12,-17684.7,4.79112], Tmin=(250,'K'), Tmax=(995.04,'K')),
            NASAPolynomial(coeffs=[4.96089,0.00375079,-1.20671e-06,1.79921e-10,-1.01857e-14,-18168.5,-1.76886], Tmin=(995.04,'K'), Tmax=(5000,'K')),
        ],
        Tmin = (250,'K'),
        Tmax = (5000,'K'),
    ),
    shortDesc = """Primary Thermo Library: KlippensteinH2O2 (Species ID: H2O2).
OO
Imported from CombFlame2014/711-Allen/thermo.txt.""",
    longDesc = 
"""
Formula: H2O2
Species name in model: H2O2(22)
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
            NASAPolynomial(coeffs=[3.97229,-0.00214266,1.29955e-05,-1.36518e-08,4.58794e-12,330.556,5.06644], Tmin=(250,'K'), Tmax=(995.04,'K')),
            NASAPolynomial(coeffs=[3.9132,0.00256254,-8.32319e-07,1.24953e-10,-7.10692e-15,121.142,4.23984], Tmin=(995.04,'K'), Tmax=(5000,'K')),
        ],
        Tmin = (250,'K'),
        Tmax = (5000,'K'),
    ),
    shortDesc = """Primary Thermo Library: KlippensteinH2O2 (Species ID: HO2).
[O]O
Imported from CombFlame2014/711-Allen/thermo.txt.""",
    longDesc = 
"""
Formula: HO2
Species name in model: HO2(21)
_auto-generated from kinetic-models database.
""",
)


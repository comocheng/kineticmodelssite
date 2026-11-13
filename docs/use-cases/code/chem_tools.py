"""Thermochemistry and rate coefficients from the records of the Prometheus API (SI units).

A thermochemistry entry (/api/thermo/) gives two NASA 7-coefficient polynomials. A rate record
(/api/kinetics/) gives its rate parameters in `data`; `a_si` and `e_si` are in SI units.
A pressure-dependent rate is calculated for a bath gas with a collision efficiency of 1.
"""
import math
from collections import defaultdict

R = 8.314462618  # J/(mol K)


def nasa(entry, T):
    """The NASA polynomial of a thermochemistry entry that applies at T."""
    if T <= entry["temp_max_1"] or not entry["coeffs_poly2"]:
        return entry["coeffs_poly1"]
    return entry["coeffs_poly2"]


def cp_over_r(entry, T):
    a = nasa(entry, T)
    return a[0] + a[1] * T + a[2] * T**2 + a[3] * T**3 + a[4] * T**4


def h_kj(entry, T=298.15):
    """Enthalpy at T in kJ/mol. At 298.15 K, this is the enthalpy of formation."""
    a = nasa(entry, T)
    return R * T * (a[0] + a[1] * T / 2 + a[2] * T**2 / 3 + a[3] * T**3 / 4 + a[4] * T**4 / 5 + a[5] / T) / 1000


def _arrhenius(d, T):
    if d["type"] == "multi_arrhenius":
        return sum(_arrhenius(x, T) for x in d["arrhenius_set"])
    return d["a_si"] * T ** d["n"] * math.exp(-d["e_si"] / (R * T))


def _plog(d, T, P):
    by_p = defaultdict(float)
    for e in d["pressure_set"]:
        by_p[e["pressure"]] += _arrhenius(e["arrhenius"], T)
    ps = sorted(by_p)
    if P <= ps[0] or P >= ps[-1]:
        return by_p[ps[0] if P <= ps[0] else ps[-1]]
    hi = next(p for p in ps if p >= P)
    lo = ps[ps.index(hi) - 1]
    k_lo, k_hi = by_p[lo], by_p[hi]
    f = math.log(P / lo) / math.log(hi / lo)
    return k_lo * (k_hi / k_lo) ** f


def rate_k(record, T, P=1e5):
    """Rate coefficient of one rate record at T (K) and P (Pa), in SI units."""
    d = record["data"]
    t = d["type"]
    if t in ("arrhenius", "multi_arrhenius"):
        return _arrhenius(d, T)
    if t == "pdep_arrhenius":
        return _plog(d, T, P)
    if t == "multi_pdep_arrhenius":
        return sum(_plog(x, T, P) for x in d["pdep_arrhenius_set"])
    if t == "chebyshev":
        tmin, tmax, pmin, pmax = record["min_temp"], record["max_temp"], record["min_pressure"], record["max_pressure"]
        T, P = min(max(T, tmin), tmax), min(max(P, pmin), pmax)
        tr = (2 / T - 1 / tmin - 1 / tmax) / (1 / tmax - 1 / tmin)
        pr = (2 * math.log10(P) - math.log10(pmin) - math.log10(pmax)) / (math.log10(pmax) - math.log10(pmin))
        c = d["coefficient_matrix"]
        cheb = lambda n, x: math.cos(n * math.acos(max(-1.0, min(1.0, x))))
        log_k = sum(c[i][j] * cheb(i, tr) * cheb(j, pr) for i in range(len(c)) for j in range(len(c[0])))
        return 10 ** log_k * {"s^-1": 1.0, "cm^3/(mol*s)": 1e-6, "cm^6/(mol^2*s)": 1e-12}[d["units"]]
    M = P / (R * T)  # concentration of the bath gas, mol/m3
    k0 = _arrhenius(d["low_arrhenius"], T)
    if t == "third_body":
        return k0 * M
    kinf = _arrhenius(d["high_arrhenius"], T)
    pr = k0 * M / kinf
    f = 1.0
    if t == "troe":
        ex = lambda t_: math.exp(-T / t_) if t_ else 0.0
        fc = (1 - d["alpha"]) * ex(d["t3"]) + d["alpha"] * ex(d["t1"]) + (math.exp(-d["t2"] / T) if d.get("t2") else 0.0)
        lfc = math.log10(max(fc, 1e-300))
        c, n = -0.4 - 0.67 * lfc, 0.75 - 1.27 * lfc
        x = math.log10(max(pr, 1e-300)) + c
        f = 10 ** (lfc / (1 + (x / (n - 0.14 * x)) ** 2))
    return kinf * pr / (1 + pr) * f


def to_cgs(k_si, order):
    """A rate coefficient from SI units to cm3, mol and s, for a reaction of this order."""
    return k_si * 1e6 ** (order - 1)

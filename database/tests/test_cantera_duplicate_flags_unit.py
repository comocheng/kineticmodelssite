"""The duplicate flags of the Cantera export, as Gasoline_2 needs them. ck2yaml wraps a long
equation onto a second line, and the YAML patcher used to read only the first line:
IC6H13CHO-D + CH3O2 <=> CH3O2H + IC6H13CO-D and ... + AC6H12CHO-D both read as
IC6H13CHO-D + CH3O2 <=> CH3O2H +, so each got `duplicate: true`. Cantera then removed one
false flag per load, and stopped after 50; Gasoline_2 had 108."""
import os
import re
import tempfile

import yaml
from django.test import SimpleTestCase

from database.services import exports

COMPOSITION = {
    "IC6H13CHO-D(873)": {"C": 7, "H": 14, "O": 1},
    "CH3O2(46)": {"C": 1, "H": 3, "O": 2},
    "CH3O2H(80)": {"C": 1, "H": 4, "O": 2},
    "C#CC(14)": {"C": 3, "H": 4},
    "H(5)": {"H": 1},
    "C*CC.(15)": {"C": 3, "H": 5},
    "C#C-C(17)": {"C": 3, "H": 4},
}
# The radicals of IC6H13CHO-D: more than the 50 loads Cantera is given to clear false flags.
RADICALS = [f"R{k:02d}C6H12CHO-D({900 + k})" for k in range(60)]
COMPOSITION.update({name: {"C": 7, "H": 13, "O": 1} for name in RADICALS})
ABSTRACTION = "IC6H13CHO-D(873)+CH3O2(46)<=>CH3O2H(80)+{}"


def nasa7(name, composition):
    """A CHEMKIN thermo entry with a constant heat capacity."""
    elements = "".join(f"{element:<2}{count:>3}" for element, count in composition.items())
    first = f"{name:<24}{elements:<20}G{300.0:>10.3f}{5000.0:>10.3f}{1000.0:>8.2f}"
    number = "{:15.8E}".format
    return "\n".join([
        f"{first:<79}1",
        number(2.5) + number(0) * 4 + "    2",
        number(0) * 2 + number(2.5) + number(0) * 2 + "    3",
        number(0) * 4 + " " * 15 + "    4",
    ])


def ck2yaml(reactions):
    """The Cantera YAML that ck2yaml writes for these CHEMKIN reaction lines."""
    with tempfile.TemporaryDirectory() as directory:
        paths = {name: os.path.join(directory, name) for name in ("chem.inp", "therm.dat", "out.yaml")}
        with open(paths["chem.inp"], "w") as handle:
            handle.write("ELEMENTS C H O END\nSPECIES\n" + "\n".join(COMPOSITION) + "\nEND\n")
            handle.write("REACTIONS\n" + "\n".join(reactions) + "\nEND\n")
        with open(paths["therm.dat"], "w") as handle:
            handle.write("THERMO ALL\n   300.000  1000.000  5000.000\n")
            handle.write("\n".join(nasa7(n, c) for n, c in COMPOSITION.items()) + "\nEND\n")
        exports._run_ck2yaml(paths["chem.inp"], paths["therm.dat"], "", paths["out.yaml"])
        with open(paths["out.yaml"], "rb") as handle:
            return handle.read()


def flags(content):
    """(equation, duplicate or not) of each reaction, read by a YAML parser."""
    return [(r["equation"], bool(r.get("duplicate"))) for r in yaml.safe_load(content)["reactions"]]


class CanteraDuplicateFlagTests(SimpleTestCase):
    def test_the_equations_are_wrapped(self):
        # Otherwise the tests below would not test the wrapping.
        content = ck2yaml([ABSTRACTION.format(RADICALS[0]) + " 2.8E+12 0.0 13600"]).decode()
        self.assertRegex(content, r"equation: IC6H13CHO-D\(873\) \+ CH3O2\(46\) <=> CH3O2H\(80\) \+ *\n +R00")

    def test_reactions_that_share_the_first_line_are_not_flagged(self):
        content = ck2yaml([ABSTRACTION.format(name) + " 3610 2.55 10530" for name in RADICALS[:3]])
        patched = exports._patch_duplicate_reactions_yaml(content)
        self.assertEqual(patched, content)
        self.assertEqual([duplicate for _, duplicate in flags(patched)], [False] * 3)

    def test_a_species_with_a_hash_keeps_its_name(self):
        # C*CC.(15) <=> H(5) + C#CC(14) is not C*CC.(15) <=> H(5) + C#C-C(17), as MatheuCH4 has them.
        content = ck2yaml(["C*CC.(15)<=>H(5)+C#CC(14) 1E13 0 0", "C*CC.(15)<=>H(5)+C#C-C(17) 1E13 0 0"])
        self.assertEqual(exports._patch_duplicate_reactions_yaml(content), content)

    def test_a_wrapped_duplicate_is_flagged_after_the_whole_equation(self):
        equation = ABSTRACTION.format(RADICALS[0])
        content = ck2yaml([equation + " 2.8E+12 0.0 13600", equation + " 1.0E+11 0.0 9000",
                           ABSTRACTION.format(RADICALS[1]) + " 3610 2.55 10530"])
        patched = exports._patch_duplicate_reactions_yaml(content)
        self.assertEqual([duplicate for _, duplicate in flags(patched)], [True, True, False])
        self.assertEqual(len(re.findall(r"\n +R00C6H12CHO-D\(900\) +# Reaction \d\n  duplicate: true\n",
                                        patched.decode())), 2)
        import cantera as ct
        self.assertEqual(ct.Solution(yaml=patched.decode()).n_reactions, 3)

    def test_sixty_wrapped_reactions_load(self):
        import cantera as ct
        content = ck2yaml([ABSTRACTION.format(name) + " 3610 2.55 10530" for name in RADICALS])
        content = exports._fix_duplicate_issues_with_cantera(exports._patch_duplicate_reactions_yaml(content))
        self.assertEqual(ct.Solution(yaml=content.decode()).n_reactions, 60)
        self.assertNotIn(b"duplicate", content)

    def test_cantera_loop_flags_an_undeclared_duplicate_after_the_whole_equation(self):
        import cantera as ct
        equation = ABSTRACTION.format(RADICALS[0])
        content = ck2yaml([ABSTRACTION.format(RADICALS[1]) + " 3610 2.55 10530",
                           equation + " 2.8E+12 0.0 13600", equation + " 1.0E+11 0.0 9000"])
        fixed = exports._fix_duplicate_issues_with_cantera(content)
        self.assertEqual([duplicate for _, duplicate in flags(fixed)], [False, True, True])
        self.assertEqual(ct.Solution(yaml=fixed.decode()).n_reactions, 3)

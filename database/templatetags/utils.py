from django import template
from django.utils.safestring import mark_safe

register = template.Library()


@register.filter
def fields(obj):
    return [(field.verbose_name, field.value_to_string(obj)) for field in obj._meta.fields]


@register.filter
def render_thermo_table(thermo, condensed=False):
    return mark_safe(
        """
    <table class="table {condensed_class}">
        <thead>
            <tr>
                <th scope="col">#</th>
                <th scope="col">$T_{{min}}$ $(K)$</th>
                <th scope="col">$T_{{max}}$ $(K)$</th>
                <th scope="col">$a_0$</th>
                <th scope="col">$a_1$</th>
                <th scope="col">$a_2$</th>
                <th scope="col">$a_3$</th>
                <th scope="col">$a_4$</th>
                <th scope="col">$a_5$</th>
                <th scope="col">$a_6$</th>
            </tr>
        </thead>
        <tbody>
            <tr>
                <th scope="row">1</th>
                <td>{thermo.temp_min_1}</td>
                <td>{thermo.temp_max_1}</td>
                <td>{thermo.coeffs_poly1[0]}</td>
                <td>{thermo.coeffs_poly1[1]}</td>
                <td>{thermo.coeffs_poly1[2]}</td>
                <td>{thermo.coeffs_poly1[3]}</td>
                <td>{thermo.coeffs_poly1[4]}</td>
                <td>{thermo.coeffs_poly1[5]}</td>
                <td>{thermo.coeffs_poly1[6]}</td>
            </tr>
            <tr>
                <th scope="row">2</th>
                <td>{thermo.temp_min_2}</td>
                <td>{thermo.temp_max_2}</td>
                <td>{thermo.coeffs_poly2[0]}</td>
                <td>{thermo.coeffs_poly2[1]}</td>
                <td>{thermo.coeffs_poly2[2]}</td>
                <td>{thermo.coeffs_poly2[3]}</td>
                <td>{thermo.coeffs_poly2[4]}</td>
                <td>{thermo.coeffs_poly2[5]}</td>
                <td>{thermo.coeffs_poly2[6]}</td>
            </tr>
        </tbody>
    </table>
    """.format(
            thermo=thermo, condensed_class="table-condensed" if condensed else ""
        )
    )


@register.filter
def render_transport_table(transport, condensed=False):
    return mark_safe("<table></table>")

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
                <td>{thermo.Tmin1}</td>
                <td>{thermo.Tmax1}</td>
                <td>{thermo.coeff11}</td>
                <td>{thermo.coeff12}</td>
                <td>{thermo.coeff13}</td>
                <td>{thermo.coeff14}</td>
                <td>{thermo.coeff15}</td>
                <td>{thermo.coeff16}</td>
                <td>{thermo.coeff17}</td>
            </tr>
            <tr>
                <th scope="row">2</th>
                <td>{thermo.Tmin2}</td>
                <td>{thermo.Tmax2}</td>
                <td>{thermo.coeff21}</td>
                <td>{thermo.coeff22}</td>
                <td>{thermo.coeff23}</td>
                <td>{thermo.coeff24}</td>
                <td>{thermo.coeff25}</td>
                <td>{thermo.coeff26}</td>
                <td>{thermo.coeff27}</td>
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

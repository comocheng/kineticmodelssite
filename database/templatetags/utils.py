from django import template
from django.utils.safestring import mark_safe

register = template.Library()


@register.simple_tag(takes_context=True)
def param_replace(context, **kwargs):
    """
    Return encoded URL parameters that are the same as the current
    request's parameters, only with the specified GET parameters added or changed.

    It also removes any empty parameters to keep things neat,
    so you can remove a parm by setting it to ``""``.

    For example, if you're on the page ``/things/?with_frosting=true&page=5``,
    then

    <a href="/things/?{% param_replace page=3 %}">Page 3</a>

    would expand to

    <a href="/things/?with_frosting=true&page=3">Page 3</a>

    Based on
    https://stackoverflow.com/questions/22734695/next-and-before-links-for-a-django-paginated-query/22735278#22735278
    """

    get = context["request"].GET.copy()
    for k, v in kwargs.items():
        get[k] = v
    for k in [k for k, v in get.items() if not v]:
        del get[k]

    return get.urlencode()


@register.filter
def fields(obj):
    return [(field.verbose_name, field.value_to_string(obj)) for field in obj._meta.fields]


@register.filter
def pluralize(num, singular_word):
    word = singular_word if num == 1 else mark_safe(f"{singular_word}s")
    return f"{num} {word}"


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

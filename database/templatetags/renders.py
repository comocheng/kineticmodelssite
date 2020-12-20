from django import template
from django.utils.safestring import mark_safe
from database.templatetags.utils import pluralize, param_replace


register = template.Library()


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

@register.simple_tag(takes_context=True)
def render_pagination(context, objects, page_name):
    if objects.has_previous():
        first_args = param_replace(context, **{page_name: 1})
        prev_args = param_replace(context, **{page_name: objects.previous_page_number()})
        prev = """
        <li class="page-item"><a class="page-link" href="?{first_args}">First</a></li>
        <li class="page-item"><a class="page-link" href="?{prev_args}">Previous</a></li>
        """.format(
            first_args=first_args, prev_args=prev_args
        )
    else:
        prev = """
        <li class="page-item disabled"><a class="page-link" tabindex="-1" aria-disabled="true" href="#">First</a></li>
        <li class="page-item disabled"><a class="page-link" tabindex="-1" aria-disabled="true" href="#">Previous</a></li>
        """
    if objects.has_next():
        next_args = param_replace(context, **{page_name: objects.next_page_number()})
        last_args = param_replace(context, **{page_name: objects.paginator.num_pages})
        nxt = """
        <li class="page-item"><a class="page-link" href="?{next_args}">Next</a></li>
        <li class="page-item"><a class="page-link" href="?{last_args}">Last</a></li>
        """.format(
            next_args=next_args, last_args=last_args
        )
    else:
        nxt = """
        <li class="page-item disabled"><a class="page-link" tabindex="-1" aria-disabled="true" href="#">Next</a></li>
        <li class="page-item disabled"><a class="page-link" tabindex="-1" aria-disabled="true" href="#">Last</a></li>
        """

    return mark_safe(
        """
        <nav aria-label="Pagination">
            <span class="current">
                Page {objects.number} of {objects.paginator.num_pages}.
            </span>
            <ul class="pagination">
                {prev}
                {nxt}
            </ul>
        </nav>
        """.format(
            objects=objects, page_name=page_name, prev=prev, nxt=nxt
        )
    )

from django import template
from django.utils.safestring import mark_safe
from django.urls import reverse

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
                <td>{thermo.coeffs_poly1[0]:.2f}</td>
                <td>{thermo.coeffs_poly1[1]:.2f}</td>
                <td>{thermo.coeffs_poly1[2]:.2f}</td>
                <td>{thermo.coeffs_poly1[3]:.2f}</td>
                <td>{thermo.coeffs_poly1[4]:.2f}</td>
                <td>{thermo.coeffs_poly1[5]:.2f}</td>
                <td>{thermo.coeffs_poly1[6]:.2f}</td>
            </tr>
            <tr>
                <th scope="row">2</th>
                <td>{thermo.temp_min_2}</td>
                <td>{thermo.temp_max_2}</td>
                <td>{thermo.coeffs_poly2[0]:.2f}</td>
                <td>{thermo.coeffs_poly2[1]:.2f}</td>
                <td>{thermo.coeffs_poly2[2]:.2f}</td>
                <td>{thermo.coeffs_poly2[3]:.2f}</td>
                <td>{thermo.coeffs_poly2[4]:.2f}</td>
                <td>{thermo.coeffs_poly2[5]:.2f}</td>
                <td>{thermo.coeffs_poly2[6]:.2f}</td>
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


def render_reaction_list_card(reaction):
    prime_id_render = f"<p>PrIMe ID: {reaction.prime_id}</p>" if reaction.prime_id else ""
    rates = pluralize(reaction.kinetics_count, "Rate")
    models = pluralize(reaction.kinetic_model_count, "Kinetic Model")
    reaction_detail_url = reverse("reaction-detail", args=[reaction.id])
    return mark_safe(
        """
        <a
            href="{reaction_detail_url}"
            class="list-group-item list-group-item-action flex-column align-items-start"
        >
            <div class="d-flex w-100 justify-content-between">
                <h5 class="mb-1">{reaction.equation}</h5>
                <small>ID: {reaction.pk}</small>
            </div>
            {prime_id_render}
            {rates}
            <br />
            {models}
        </a>
        """.format(
            reaction=reaction,
            prime_id_render=prime_id_render,
            rates=rates,
            models=models,
            reaction_detail_url=reaction_detail_url,
        )
    )


def _render_card_list(card_render_func, objects, **kwargs):
    cards = "\n".join(card_render_func(o) for o in objects)

    return mark_safe(
        f"""
        <div class="list-group">
            {cards}
        </div>
        """
    )


@register.filter
def render_reaction_list(reactions):
    return _render_card_list(render_reaction_list_card, reactions)


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
        <li class="page-item disabled">
            <a class="page-link" tabindex="-1" aria-disabled="true" href="#">First</a>
        </li>
        <li class="page-item disabled">
            <a class="page-link" tabindex="-1" aria-disabled="true" href="#">Previous</a>
        </li>
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
        <li class="page-item disabled">
            <a class="page-link" tabindex="-1" aria-disabled="true" href="#">Next</a>
        </li>
        <li class="page-item disabled">
            <a class="page-link" tabindex="-1" aria-disabled="true" href="#">Last</a>
        </li>
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
            objects=objects, prev=prev, nxt=nxt
        )
    )


def render_species_list_card(species):
    if species.names:
        names_inner = "\n".join(
            f"<li class='list-group-item'>{name}</li>" for name in species.names
        )
        names_render = f"""
        <h6>Names</h6>
        <ul class="list-group">
            {names_inner}
        </ul>
        <br />
        """.strip()
    else:
        names_render = ""

    if species.structures:
        structures_inner = "\n".join(
            f"""
            <li class='list-group-item'>
                <img src='{reverse('draw-structure', args=[structure.pk])}'/>
            </li>
            """.strip()
            for structure in species.structures
        )
        structures_render = f"""
        <h6>Structures</h6>
        <ul class="list-group">
            {structures_inner}
        </ul>
        """.strip()
    else:
        structures_render = ""

    return mark_safe(
        f"""
        <a
            href="{reverse('species-detail', args=[species.pk])}"
            class="list-group-item list-group-item-action flex-column align-items-start"
        >
        <div class="d-flex w-100 justify-content-between">
            <h5 class="mb-1">{species.formula}</h5>
            <small>ID: {species.pk}</small>
        </div>
        {names_render}
        {structures_render}
        </a>
        """.strip()
    )


@register.filter
def render_species_list(species):
    return _render_card_list(render_species_list_card, species)


@register.filter
def render_kinetics_list_card(kinetics, is_comment=False):
    if is_comment:
        comment = kinetics.comment
        kinetics = kinetics.kinetics
    else:
        comment = None

    reaction_url = reverse("reaction-detail", args=[kinetics.reaction.pk])
    if kinetics.reaction.prime_id:
        prime_id_render = f"<p>PrIMe ID: {kinetics.reaction.prime_id}</p>"
    else:
        prime_id_render = ""
    comment_render = f"<p>{comment}</p>" if is_comment and comment else ""
    table = kinetics.data.table_data()[-1]
    heads = "\n".join(f"<th scope='col'>{head}</th>" for head in table[1])
    head = f"""
    <thead>
        {heads}
    </thead>
    """.strip()
    bodies = []
    for row_header, cells in table[2]:
        row_header_render = f"<th scope='row'>{row_header}</th>" if row_header else ""
        cell_render = "\n".join(f"<td>{cell}<td>" for cell in cells)
        bodies.append(
            f"""
            <tbody>
                <tr>
                    {row_header_render}
                    {cell_render}
                </tr>
            </tbody>
            """.strip()
        )
    bodies_render = "\n".join(bodies)

    return mark_safe(
        f"""
        <div class="card">
            <a href="{reaction_url}"
            class="list-group-item list-group-item-action flex-column align-items-start"
            >
                <div class="d-flex w-100 justify-content-between">
                    <h5 class="mb-1">{kinetics.reaction.equation}</h5>
                    <small>ID: {kinetics.reaction.pk}</small>
                </div>
                {prime_id_render}
                {comment_render}
                <small>{kinetics.data.kinetics_type}</small>
                <table class="table table-condensed">
                    {head}
                    {bodies_render}
                </table>
            </a>
        </div>
        """.strip()
    )


@register.filter
def render_kinetics_list(kinetics, is_comment=True):
    return _render_card_list(render_kinetics_list_card, kinetics, is_comment=is_comment)


def render_thermo_list_card(thermo):
    models = thermo.kineticmodel_set.all()
    if models:
        model_renders = "\n".join(
            (
                '<a class="list-group-item list-group-item-action flex-column align-items-start"'
                f'href="{reverse("kinetic-model-detail", args=[model.pk])}">{model.model_name}</a>'
            )
            for model in models
        )
        models_render = f"""
        <h6>Models</h6>
        <div class="list-group">
            {model_renders}
        </div>
        """.strip()
    else:
        models_render = ""
    thermo_url = reverse("thermo-detail", args=[thermo.pk])
    return mark_safe(
        fr"""
        <div class="list-group-item list-group-item-action flex-column align-items-start">
            <a href="{thermo_url}"
                class="list-group-item-action"
            >
                <div class="d-flex w-100 justify-content-between">
                    <h5 class="mb-1">
                        $\Delta H_f \, (298 \, K):{thermo.enthalpy298:.1f} \, \frac{{J}}{{mol}}$
                        <br>
                        $S \, (298 \, K):{thermo.entropy298:.1f} \, \frac{{J}}{{mol-K}}$
                    </h5>
                    <small>ID: {thermo.pk}</small>
                </div>
                <br />
                {models_render}
            </a>
        </div>
        """
    )


@register.filter
def render_thermo_list(thermo_list):
    return _render_card_list(render_thermo_list_card, thermo_list)


def render_transport_list_card(transport):
    models = transport.kineticmodel_set.all()
    if models:
        model_renders = "\n".join(
            (
                '<a class="list-group-item list-group-item-action flex-column align-items-start"'
                f'href="{reverse("kinetic-model-detail", args=[model.pk])}">{model.model_name}</a>'
            )
            for model in models
        )
        models_render = f"""
        <br/>
        <h6>Models</h6>
        <div class="list-group">
            {model_renders}
        </div>
        """.strip()
    else:
        models_render = ""
    prime_id_render = f'<h5 class="mb-1">{transport.prime_id}</h5>' if transport.prime_id else ""
    info_render = fr"""
    <br />
    <ul class="list-group">
        <li class="list-group-item">Geometry: {transport.geometry}</li>
        <li class="list-group-item">
            Potential Well Depth: $\SI{{{transport.potential_well_depth}}}{{K}}$
        </li>
        <li class="list-group-item">
            Collision Diameter: $\SI{{{transport.collision_diameter}}}{{\angstrom}}$
        </li>
        <li class="list-group-item">Dipole Moment: $\SI{{{transport.dipole_moment}}}{{\debye}}$</li>
        <li class="list-group-item">
            Polarizability: $\SI{{{transport.polarizability}}}{{\angstrom^3}}$
        </li>
        <li class="list-group-item">
            Rotational Relaxation: ${transport.rotational_relaxation}$
        </li>
    </ul>
    """
    transport_url = reverse("transport_detail", args=[transport.pk])
    return mark_safe(
        fr"""
        <div class="list-group-item list-group-item-action flex-column align-items-start">
            <a href="{transport_url}"
                class="list-group-item-action"
            >
                <div class="d-flex w-100 justify-content-between">
                    {prime_id_render}
                    <small>ID: {transport.pk}</small>
                </div>
                {info_render}
                {models_render}
            </a>
        </div>
        """.strip()
    )


@register.filter
def render_transport_list(transport_list):
    return _render_card_list(render_transport_list_card, transport_list)

"""
Checks of the ontology and the templates:

    pip install pytest rdflib
    pytest tests

Every file parses; every Element Template's constitutive relation is well-formed MathML naming only its own
parameters, its domain's constants and the element's port variables; a template that names its law (bgf:lawLabel)
also says how it is drawn (bgf:hasStyle), and no two templates of the same element class and domain are drawn alike;
the new laws reduce to the existing ones in their limits.
"""
import glob
import math
import os
import xml.etree.ElementTree as ET

import pytest
from rdflib import Graph, Namespace, RDF, RDFS, URIRef

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BGF = Namespace('https://bg-rdf.org/ontologies/bondgraph-framework#')
MATHML = '{http://www.w3.org/1998/Math/MathML}'
TEMPLATES = sorted(glob.glob(os.path.join(ROOT, 'templates', '*.ttl')))
# the variables an element's relation may use besides its parameters and its domain's constants
PORT_VARIABLES = {'t', 'q', 'u', 'v', 'u_f', 'u_r', 'v_f', 'v_r', 'p'}


@pytest.fixture(scope='module')
def graph():
    g = Graph()
    g.parse(os.path.join(ROOT, 'schema', 'ontology.ttl'))
    for path in TEMPLATES:
        g.parse(path)
    return g


@pytest.mark.parametrize('path', [os.path.join(ROOT, 'schema', 'ontology.ttl')] + TEMPLATES,
                         ids=lambda p: os.path.relpath(p, ROOT))
def test_every_file_parses(path):
    assert len(Graph().parse(path)) > 0


def _templates(g):
    return sorted(set(g.subjects(RDF.type, BGF.ElementTemplate)))


def _names(g, node, predicate):
    return {str(g.value(b, BGF.varName)) for b in g.objects(node, predicate)}


def _relation(g, template):
    for cls in [template] + list(g.transitive_objects(template, RDFS.subClassOf)):
        r = g.value(cls, BGF.constitutiveRelation)
        if r is not None:
            return str(r)


def test_transformers_and_gyrators_are_transform_nodes(graph):
    '''A transform node can say which it is, so a transformer between physical domains (charge moved across a
    membrane: chemical potential = z F x electrical potential) is not taken for a gyrator.'''
    for kind in (BGF.TransformerNode, BGF.GyratorNode):
        assert (kind, RDFS.subClassOf, BGF.TransformNode) in graph
        assert graph.value(kind, RDFS.label) is not None


def test_variable_naming_is_described(graph):
    '''A model can name its variables in generated code: rules by element class and variable, and explicit names.'''
    for prop in ('hasNamingRule', 'forElementClass', 'forDomain', 'forVariable', 'namePattern', 'hasVariableName',
                 'cellmlName'):
        assert (BGF[prop], RDF.type, None) in graph, prop
    assert graph.value(BGF.hasNamingRule, RDFS.range) == BGF.NamingRule
    assert graph.value(BGF.hasVariableName, RDFS.range) == BGF.VariableName
    for placeholder in ('{species}', '{location}', '{name}', '{element}', '{label}', '{var}'):
        assert placeholder in str(graph.value(BGF.NamingRule, URIRef('http://purl.org/dc/terms/description')))


def test_each_template_is_defined_once(graph):
    '''A template has at most one label, constitutive relation, law label and style (the ontology's functional
    properties): a second definition of the same name in the templates would give it two.'''
    for t in _templates(graph):
        for p in (RDFS.label, BGF.constitutiveRelation, BGF.lawLabel, BGF.hasStyle):
            assert len(list(graph.objects(t, p))) <= 1, f'{t}: more than one {p}'


def test_constitutive_relations_are_mathml_over_known_names(graph):
    for t in _templates(graph):
        relation = _relation(graph, t)
        if relation is None:
            continue
        math_el = ET.fromstring(relation.strip())
        assert math_el.tag == MATHML + 'math', t
        domain = graph.value(t, BGF.hasDomain)
        known = _names(graph, t, BGF.hasParameter) | _names(graph, t, BGF.hasVariable) \
            | _names(graph, t, BGF.hasSignalInput) | _names(graph, t, BGF.hasSignalOutput) \
            | (_names(graph, domain, BGF.hasConstant) if domain is not None else set()) | PORT_VARIABLES
        for base in graph.transitive_objects(t, RDFS.subClassOf):
            known |= _names(graph, base, BGF.hasParameter) | _names(graph, base, BGF.hasVariable)
        used = {ci.text.strip() for ci in math_el.iter(MATHML + 'ci')}
        ports = {f'{v}_{p}' for p in (str(graph.value(b, BGF.portId)) for b in graph.objects(t, BGF.hasPort))
                 for v in ('u', 'v')}
        assert used <= known | ports, (t, used - known - ports)


def _style(g, t):
    s = g.value(t, BGF.hasStyle)
    if s is None:
        return None
    return tuple(str(g.value(s, p) or '') for p in (BGF.textColour, BGF.backgroundColour, BGF.borderColour,
                                                    BGF.borderStyle))


def _base_class(g, t):
    for base in g.objects(t, RDFS.subClassOf):
        if g.value(base, RDF.type) != BGF.ElementTemplate:
            return base


def test_a_named_law_is_drawn_distinctly(graph):
    '''A template with a law label has a style, with a border style the editor knows; within an element class
    and domain, the templates' (label, style) pairs differ, so each law can be told apart on a diagram.'''
    seen = {}
    for t in _templates(graph):
        label = graph.value(t, BGF.lawLabel)
        style = _style(graph, t)
        if label is None and style is None:
            continue
        assert label is not None and style is not None, f'{t}: give both bgf:lawLabel and bgf:hasStyle'
        assert style[3] in ('solid', 'dashed', 'double'), (t, style[3])
        key = (_base_class(graph, t), graph.value(t, BGF.hasDomain))
        assert (str(label), style) not in seen.get(key, set()), f'{t} is drawn like another template'
        seen.setdefault(key, set()).add((str(label), style))


def _evaluate(node, env):
    '''A MathML expression's value (the subset the templates use).'''
    tag = node.tag[len(MATHML):]
    if tag == 'ci':
        return env[node.text.strip()]
    if tag == 'cn':
        return float(node.text)
    assert tag == 'apply', tag
    op, *args = list(node)
    op = op.tag[len(MATHML):]
    x = [_evaluate(a, env) for a in args]
    return {'plus': lambda: sum(x), 'minus': lambda: x[0] - x[1] if len(x) == 2 else -x[0],
            'times': lambda: math.prod(x), 'divide': lambda: x[0] / x[1], 'exp': lambda: math.exp(x[0]),
            'ln': lambda: math.log(x[0]), 'power': lambda: x[0] ** x[1], 'root': lambda: math.sqrt(x[0]),
            'abs': lambda: abs(x[0]), 'max': lambda: max(x)}[op]()


def _solve(graph, template, lhs, env):
    '''The value of the relation's equation for lhs (a variable name) at env.'''
    math_el = ET.fromstring(_relation(graph, BGF[template]).strip())
    for eq in math_el.findall(MATHML + 'apply'):
        _, left, right = list(eq)
        if left.tag == MATHML + 'ci' and left.text.strip() == lhs:
            return _evaluate(right, env)
    raise KeyError(lhs)


def test_the_saturating_reaction_is_mass_action_slowed(graph):
    env = dict(kappa=2.0, sigma=5.0, u_f=1500.0, u_r=-800.0, RT=2578.73058)
    pf, pr = math.exp(env['u_f'] / env['RT']), math.exp(env['u_r'] / env['RT'])
    mass_action = _solve(graph, 'ChemicalReaction', 'v', env)
    assert mass_action == pytest.approx(env['kappa'] * (pf - pr))
    assert _solve(graph, 'SaturatingChemicalReaction', 'v', env) == pytest.approx(mass_action / (1 + (pf + pr) / 5.0))
    assert _solve(graph, 'SaturatingChemicalReaction', 'v', dict(env, sigma=1e12)) == pytest.approx(mass_action)


def test_the_saturating_store_is_ideal_while_dilute(graph):
    env = dict(K=3.0, q=1e-6, k_sat=1.0, RT=2578.73058)
    assert _solve(graph, 'SaturatingChemicalConcentration', 'u', env) == \
        pytest.approx(_solve(graph, 'ChemicalConcentration', 'u', env), abs=1e-2)
    env['q'] = 1e3   # saturated: activity tends to K k_sat
    assert _solve(graph, 'SaturatingChemicalConcentration', 'u', env) == \
        pytest.approx(env['RT'] * math.log(env['K'] * env['k_sat']), rel=1e-3)


def test_the_bernoulli_resistor_solves_its_pressure_drop(graph):
    for u in (-30.0, -0.5, 0.0, 2.0, 40.0):
        env = dict(u=u, R=4.0, B=1.5)
        v = _solve(graph, 'BernoulliHydraulicResistor', 'v', env)
        assert env['R'] * v + env['B'] * v * abs(v) == pytest.approx(u, abs=1e-12)
        assert _solve(graph, 'BernoulliHydraulicResistor', 'v', dict(env, B=0.0)) == \
            pytest.approx(_solve(graph, 'HydraulicResistor', 'v', dict(u=u, k=1.0 / env['R'])))


#===============================================================================
# Signals: blocks, signal inputs and the elements for vessel, organ and control modules

def _signal_blocks(g):
    return sorted(t for t in _templates(g) if (t, RDFS.subClassOf, BGF.SignalBlock) in g)


def test_signal_vocabulary_is_described(graph):
    '''Signal blocks, signal bonds' properties and template signal inputs and outputs are in the ontology.'''
    for name in ('SignalBlock', 'SignalBond', 'SignalDomain', 'hasSignalBlock', 'hasSignalBond', 'hasSignalInput',
                 'hasSignalOutput', 'unitsOf', 'signalVariable', 'signalInput', 'modulates', 'modulationExponent',
                 'portType'):
        assert (BGF[name], RDF.type, None) in graph, name


def test_signal_blocks_have_one_output_and_resolvable_units(graph):
    '''A block has one output and is in the signal domain; every bgf:unitsOf names one of its own variables, and
    a variable that has neither units nor bgf:unitsOf is an input (its source's units) or a parameter (its value's).'''
    blocks = _signal_blocks(graph)
    assert {str(b).rsplit('#', 1)[1] for b in blocks} >= {
        'FirstOrderLag', 'SigmoidMap', 'SaturatingScale', 'LogisticScale', 'PowerLaw', 'LinearMap', 'Product', 'Sum',
        'OsmoticPressure', 'Concentration', 'SignalInputPort', 'SignalOutputPort'}
    for b in blocks:
        assert graph.value(b, BGF.hasDomain) == BGF.Signal, b
        assert len(list(graph.objects(b, BGF.hasSignalOutput))) == 1, b
        own = _names(graph, b, BGF.hasParameter) | _names(graph, b, BGF.hasSignalInput) \
            | _names(graph, b, BGF.hasSignalOutput)
        for predicate in (BGF.hasParameter, BGF.hasSignalInput, BGF.hasSignalOutput):
            for v in graph.objects(b, predicate):
                units_of = graph.value(v, BGF.unitsOf)
                if units_of is not None:
                    assert str(units_of) in own, (b, units_of)
                    assert graph.value(v, BGF.hasUnits) is None, (b, 'both units and unitsOf')
                elif graph.value(v, BGF.hasUnits) is None:
                    assert predicate != BGF.hasSignalOutput or b == BGF.SignalInputPort, (b, 'output without units')


def test_elements_with_signal_inputs_fix_their_units(graph):
    '''A bond element's signal inputs have fixed units, so a signal of other units is an error, not a silent
    rescaling.'''
    for t in _templates(graph):
        if (t, RDFS.subClassOf, BGF.SignalBlock) in graph:
            continue
        for v in graph.objects(t, BGF.hasSignalInput):
            assert graph.value(v, BGF.hasUnits) is not None, (t, graph.value(v, BGF.varName))


def test_the_compliances_are_linear_and_the_viscous_wall_adds_its_rate(graph):
    env = dict(q=1.3, q_us=0.8, C=0.05, R_v=2.0, v=0.4)
    assert _solve(graph, 'HydraulicCompliance', 'u', env) == pytest.approx((1.3 - 0.8) / 0.05)
    assert _solve(graph, 'ViscoelasticHydraulicCompliance', 'u', env) == pytest.approx((1.3 - 0.8) / 0.05 + 0.8)


def test_the_one_way_resistance_passes_flow_only_above_the_opposing_pressure(graph):
    assert _solve(graph, 'RectifyingHydraulicResistor', 'v', dict(k=0.5, u=3.0, u_0=1.0)) == pytest.approx(1.0)
    assert _solve(graph, 'RectifyingHydraulicResistor', 'v', dict(k=0.5, u=0.5, u_0=1.0)) == 0.0
    assert _solve(graph, 'RectifyingHydraulicResistor', 'v', dict(k=0.5, u=3.0, u_0=0.0)) == \
        pytest.approx(_solve(graph, 'HydraulicResistor', 'v', dict(k=0.5, u=3.0)))


def test_michaelis_menten_saturates_in_its_substrate_and_scales_with_the_enzyme(graph):
    RT = 2578.73058
    env = dict(kcat=1.0, a=1.0, E=2e-12, Km=1.1, u_f=RT * math.log(1.1), RT=RT)
    assert _solve(graph, 'MichaelisMentenReaction', 'v', env) == pytest.approx(1e-12)   # half of kcat E at Km
    assert _solve(graph, 'MichaelisMentenReaction', 'v', dict(env, a=0.25, u_f=RT * 30)) == \
        pytest.approx(0.25 * 2e-12, rel=1e-9)


def test_kedem_katchalsky_reduces_to_osmosis_and_to_diffusion_plus_convection(graph):
    w = dict(Lp=0.2, sigma=1.0, u_water_in=5.0, u_water_out=1.0, Pi_in=30.0, Pi_out=33.0)
    assert _solve(graph, 'KedemKatchalskyWaterFlux', 'v', w) == pytest.approx(0.2 * (4.0 + 3.0))
    s = dict(omega=0.01, sigma=0.3, c_in=0.15, c_out=0.12, Jv=0.5)
    assert _solve(graph, 'KedemKatchalskySoluteFlux', 'v', s) == \
        pytest.approx(0.01 * 0.03 + 0.7 * 0.135 * 0.5)
    assert _solve(graph, 'KedemKatchalskySoluteFlux', 'v', dict(s, sigma=1.0, Jv=99.0)) == pytest.approx(0.01 * 0.03)
    assert _solve(graph, 'ConvectiveSoluteFlux', 'v', dict(c=0.15, Jv=0.5)) == pytest.approx(0.075)


def test_signal_blocks_compute_the_control_laws(graph):
    '''The forms of the BVC-RAAS models: Ang II scaling, the renin pressure threshold and feedback power law, the
    baroreceptor sigmoid.'''
    assert _solve(graph, 'SaturatingScale', 'y', dict(alpha=0.5, u=2.0, u_half=2.0)) == pytest.approx(1.25)
    assert _solve(graph, 'LogisticScale', 'y', dict(a=4.0, u=11.0, u_th=11.0, w=1.0)) == pytest.approx(3.0)
    assert _solve(graph, 'PowerLaw', 'y', dict(u=2.0, u_ref=1.0, n=-0.95)) == pytest.approx(2.0 ** -0.95)
    f = _solve(graph, 'SigmoidMap', 'y', dict(u=13.0, u_nom=12.0, k=1.6, y_min=2.52, y_max=47.78))
    e = math.exp(1.0 / 1.6)
    assert f == pytest.approx((2.52 + 47.78 * e) / (1 + e))
    assert _solve(graph, 'LinearMap', 'y', dict(a=0.2, b=0.8, u=1.5)) == pytest.approx(1.4)
    assert _solve(graph, 'OsmoticPressure', 'y', dict(phi=2.0, RT=2578.73058, q_s=0.14, q_w=1.0)) == \
        pytest.approx(2 * 2578.73058 * 0.14)

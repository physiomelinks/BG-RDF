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
            | _names(graph, domain, BGF.hasConstant) | PORT_VARIABLES
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
            'abs': lambda: abs(x[0])}[op]()


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

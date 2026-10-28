# BG-RDF – a Framework for Bond-Graph Modelling

> [!WARNING]
> This framework is actively being developed and nothing should be considered stable until version `1.0` has been released.

## Documentation:

* [BG-RDF Ontology](https://bg-rdf.org/ontologies/bondgraph-framework)

## BG-RDF SPARQL endpoint:

1. Install the [Oxigraph CLI](https://crates.io/crates/oxigraph-cli) tool.
2. Clone this repository.
3. Run `./server.sh`.

## Choosing a constitutive relation:

An element's constitutive relation comes from its Element Template (`templates/*.ttl`): a
Reaction, Resistance or store can be any template of its class in its domain, e.g. a
`bgf:ChemicalReaction` (mass action) or a `bgf:SaturatingChemicalReaction`. A template whose
relation is not its domain's default names it with `bgf:lawLabel` (a short tag drawn with the
element's symbol) and says how it is drawn with `bgf:hasStyle`, a `bgf:ElementStyle`
(`bgf:textColour`, `bgf:backgroundColour`, `bgf:borderColour`, `bgf:borderStyle` of `solid`,
`dashed` or `double`), so elements with different relations look different on a diagram.

| Template | Element | Relation | Law label |
|---|---|---|---|
| `bgf:ChemicalReaction` | Reaction | `v = kappa (exp(u_f/RT) - exp(u_r/RT))` | |
| `bgf:SaturatingChemicalReaction` | Reaction | the same over `1 + (exp(u_f/RT) + exp(u_r/RT))/sigma` | sat |
| `bgf:ChemicalConcentration` | QuantityStore | `u = RT ln(K q)` | |
| `bgf:SaturatingChemicalConcentration` | QuantityStore | `u = RT ln(K q k_sat/(k_sat + q))` | sat |
| `bgf:HydraulicResistor` | Resistance | `v = k u` | |
| `bgf:BernoulliHydraulicResistor` | Resistance | `u = R v + B v abs(v)`, solved for `v` | PB |

A `bgf:TransformNode` whose ports are in different physical domains is taken to be a gyrator. Say
which it is with `bgf:TransformerNode` or `bgf:GyratorNode`. A reaction that moves charge q across a
membrane is coupled to the membrane's capacitor through transformers of ratio q F, which turn the
membrane potential into a chemical potential (electrogenic transport).

`pytest tests` checks the ontology and templates (`pip install pytest rdflib`).

## Naming variables in generated code:

A model's variables are named after its elements (`q_G6P_c`, `u_q_G6P_c`, `v_Re_HK_c`). A model may name them
another way: a `bgf:NamingRule` names one variable of one class of element by a pattern, and a
`bgf:VariableName` on an element names one of its variables explicitly:

```turtle
<> bgf:hasNamingRule [ bgf:forElementClass bgf:QuantityStore ; bgf:forVariable "q" ;
                       bgf:namePattern "n_{species}_{location}" ] .
:Re_HK bgf:hasVariableName [ bgf:forVariable "v" ; bgf:cellmlName "v_hexokinase" ] .
```

## Tools:

* **[bg2cellml](https://github.com/CellDL/BG-Tools)**: a Python utility to generate CellML from BG-RDF models.
* **[CellDL Editor](https://github.com/CellDL/CellDLEditor)**: A Vue 3 component and standalone editor to create SVG diagrams containing BG-RDF models.

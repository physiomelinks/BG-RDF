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
| `bgf:HydraulicCompliance` | QuantityStore | `u = (q - q_us)/C + u_ext` | C |
| `bgf:ViscoelasticHydraulicCompliance` | QuantityStore | `u = (q - q_us)/C + R_v v + u_ext` | VE |
| `bgf:ElasticVessel` | QuantityStore | `u = E (q - q_hat)/(q_bar - q)^2` (stiffens near `q_bar`) | |
| `bgf:HydraulicInertance` | FlowStore | `dv/dt = u/I` | |
| `bgf:ResistiveHydraulicInertance` | FlowStore | `dv/dt = (u - R v)/I` | RI |
| `bgf:RectifyingHydraulicResistor` | Resistance | `v = k max(u - u_0, 0)` | max |
| `bgf:KedemKatchalskyWaterFlux` | Reaction | `v = Lp ((u_in - u_out) - sigma (Pi_in - Pi_out))`, `Pi` signals | KK |
| `bgf:KedemKatchalskySoluteFlux` | Reaction | `v = omega (c_in - c_out) + (1 - sigma)(c_in + c_out)/2 Jv`, `c`, `Jv` signals | KK |
| `bgf:ConvectiveSoluteFlux` | Reaction | `v = c Jv`, signals | cv |
| `bgf:MichaelisMentenReaction` | Reaction | `v = kcat a E x/(x + Km)`, `x = exp(u_f/RT)`, enzyme `E` a signal | MM |
| `bgf:SignalFlux`, `bgf:SignalWaterFlux` | Reaction | `v = J`, a signal (a flow between two nodes that a law of signal blocks sets) | set |
| `bgf:NKEPump` | Reaction | Na/K-ATPase's Na flux `3 k_NKE (K_ATP n_i^3 k_o^2 - n_o^3 k_i^2 exp(2 F u_e/RT))/((1 + n_i^3)(1 + n_o^3)(1 + k_o^2)(1 + k_i^2))`, `n = K_Na c_Na`, `k = K_K c_K`, concentrations signals | NKE |

A `bgf:TransformNode` whose ports are in different physical domains is taken to be a gyrator. Say
which it is with `bgf:TransformerNode` or `bgf:GyratorNode`. A reaction that moves charge q across a
membrane is coupled to the membrane's capacitor through transformers of ratio q F, which turn the
membrane potential into a chemical potential (electrogenic transport).

`pytest tests` checks the ontology and templates (`pip install pytest rdflib`).

## Signals:

A `bgf:SignalBond` carries a variable of its source (`bgf:hasSource`: a bond element, a junction or a
`bgf:SignalBlock`) to its target (`bgf:hasTarget`), where it either sets a signal input of the target's template
(`bgf:hasSignalInput`; the bond's `bgf:signalInput` names it, else the first not otherwise connected) or scales one
of its parameters (`bgf:modulates`: in the constitutive relation `p` becomes `p s^n`, `n` the bond's
`bgf:modulationExponent`, 1 by default). A `bgf:signalInput` naming one of the target's parameters (or a source's
value, `v` or `u`) sets it from the signal instead of a value. `bgf:signalVariable` picks the source's variable (`q`, `u` or `v`); by
default a store's quantity, a flow store's, resistance's or reaction's flow, a source's value, a 0-junction's
potential, a 1-junction's flow and a block's output. A model lists its blocks with `bgf:hasSignalBlock` and its
signal bonds with `bgf:hasSignalBond`.

Signal blocks (`templates/signal.ttl`) each compute one output `y`, so control laws are chains of them:
`FirstOrderLag` (`dy/dt = (u - y)/tau`), `SigmoidMap` (`y = (y_min + y_max e^x)/(1 + e^x)`, `x = (u - u_nom)/k`),
`SaturatingScale` (`y = 1 + alpha u/(u + u_half)`), `LogisticScale` (`y = 1 + a/(1 + exp((u - u_th)/w))`),
`PowerLaw` (`y = (u/u_ref)^n`), `LinearMap` (`y = a + b u`), `Product`, `Sum`, `OsmoticPressure`
(`y = phi RT q_s/q_w`), `Concentration` (`y = q_s/q_w`), `VantHoff` (`y = phi RT c`), `Constant` (`y` is the
block's value, a parameter several elements can share through signals that set their parameters), `Gain`
(`y = k u`, `k` of any units), `Difference` (`y = u_1 - u_2`), `Ratio` (`y = u_1/u_2`), `Rectifier`
(`y = max(u, 0)`), `Integrator` (`dy/dt = u`, from the block's value), and `SignalInputPort` and `SignalOutputPort`,
a model's signals from and to outside it (a module's entrance and exit ports, of type `bgf:portType`). A block's
variable has fixed units, those of another of its variables or of a product or quotient of two (`bgf:unitsOf`
`"u"`, `"k*u"`, `"u_1/u_2"`), or its source's (an input) or its value's (a parameter, a constant's output).

A resistance or reaction with `bgf:oneWay true` passes flow only forwards: its flow is `max(v, 0)`.

A model in other units than the templates' says so with `bgf:unitSystem`: `"SI"` has cubic metres for litres and
Pa for kPa (`<model> bgf:unitSystem "SI"`). A value given in other units of the same kind (`"6.0e-9 m6/J"`,
`"0.5 kPa"`) is converted to its variable's.

### Module ports:

Any element or block with a `bgf:portType` is part of a module port of that type. `bgf:portVariables` names the
variables it gives the port, in order (`"v"`, `"q"`, `"u v"`, ...; by default a source's flow and potential, a block's
output, a store's quantity, another element's flow), `bgf:portDirection` makes it an `"entrance"`, `"exit"` or
`"general"` port (by default a source is an entrance when its bond leaves it, an input port block an entrance and
anything else an exit), and `bgf:multiPort` gives the port's `multi_port` (`"True"`, `"sum"`). Elements with the same
port type and direction that have a `bgf:portOrder` make one port of several variables, in that order:

```turtle
:u_gl a bgf:HydraulicPotential ; bgf:hasSymbol "u_gl" ; bgf:portType "renal_bed_port" ;
    bgf:portVariables "u" ; bgf:portDirection "entrance" ; bgf:portOrder 1 .
:v_aff a bgf:SignalInputPort ; bgf:hasSymbol "v_aff" ; bgf:portType "renal_bed_port" ; bgf:portOrder 5 .
:q_pl_Na a bgf:ChemicalStorageNode ; bgf:portType "circulation_Na_port" ; bgf:portVariables "q" ;
    bgf:multiPort "True" .
```

```turtle
:Ang_scale a bgf:SaturatingScale ; bgf:hasSymbol "ang_scale" ;
    bgf:parameterValue [ bgf:varName "alpha" ; bgf:hasValue "0.5 1"^^cdt:ucum ] ,
                       [ bgf:varName "u_half" ; bgf:hasValue "1e-11 mol"^^cdt:ucum ] .
:s1 a bgf:SignalBond ; bgf:hasSource :q_ATII ; bgf:hasTarget :Ang_scale .
:s2 a bgf:SignalBond ; bgf:hasSource :Ang_scale ; bgf:hasTarget :R_eff ;
    bgf:modulates "k" ; bgf:modulationExponent -1 .        # the conductance k divided by the scale
```

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

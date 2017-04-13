"""
Reaction r1 'A -> B'
  kinetics according to model m1: (rate k1)
  kinetics according to model m2: (rate k2)
  kinetics according to model m3: (rate k2)


Reactions [ r1, ... ]
Models    [ m1, m2, m3 ]
Kinetics  [ k1, k2, ... ]


Q: which models is rate k2 used in?
A: m2 and m3

Q: Where has k2 been used?
A: for r1 in models m2 and m3
A2: ...but also for r2 and r3 in model m3 (is this relevant?) NO



#What will we do with all the extra .zip, .pdf, .hdf, and .mat files tied to
# models, sources, etc. on PrIMe?
#Basically everything has a bibliography tied to it, so I stopped listing it
# partway through
#Accordingly, probably biblio should be highest in the hierarchy because it
# has everything as a subcategory

PrIMe Fields for objects we are not yet including:
# Data Attributes
#     ******in catalog*******
#     experiment
#     features
#         indicators/observables properties
#             property values (i.e. temp, pressure)
#     data attribute values
#         indicators/observables properties
#             property values (i.e. temp, pressure)
#             for time value: upper/lower bounds
#     description
#     ******in instrumentalModels/catalog******
#     title (preferred key)
#     keywords (instrument used)
#     property values (i.e. residence time, energy control)
#     variable components (many layers, quite confusing)
#     description/additional info
# Data sets
#     ******in catalog******** (only two xmls)
#     data set title
#     model
#     surrogate models
#     data set website
#     *******in data/d00000001/surrogateModels/catalog and
#       data/d00000002/surrogateModels/catalog********
#     model
#     optimization variables with formulas and bounds
#     coefficient values with variable links
#     description
# Elements
#     ******in catalog********
#     atomic number
#     element symbol
#     element name
#     atomic mass
#     mass number
#     isotopes (for every isotope:)
#         atomic mass value
#         atomic mass uncertainty
# Experiments
#     ******in catalog*******
#     bibliographies (sometimes multiple)
#     apparatuses
#         apparatus property values
#     common property values
#         initial species composition values
#     data groups
#         properties
#             data points (about 2-4 coordinates each)
#     additional info
# Optimization Variables
#     ******in catalog********
#     reaction
#     kinetics
#     equation
#     description
#     ********in data********** (take the xml that ends in 1, not 0)
#     bibliography
#     equation
#     upper bound
#     lower bound
# Targets
#     ********in catalog*********** (components frequently vary)
#     bibliography
#     experiment
#     features
#         indicators/observables properties
#         methods/method types
#     target value and subcategories/values
#     description

    Add this to a lot of the models to make entries on the form have to be
    unique (avoid duplicates):
        class Meta:
        unique_together = ["title", "state", "name"] <-whatever the
                                            fields are that should not have
                                             multiple of the same combination

"""

# Models
#     ******in catalog*******
#     model name
#     species involved
#         thermo
#         transport
#     reactions involved
#         kinetics
#     additional info
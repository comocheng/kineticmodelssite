import pandas, logging, os, django
import pprint, time
from habanero import Crossref

# This is some magic code I cobbled together across a few StackOverflow threads to get the model imports to work
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "kineticssite.settings")
django.setup()
from kineticmodels.models import KineticModel

# Configure logging for debugging
logging.basicConfig(filename="alpha_testing.log",
                    format="%(levelname)s: %(message)s",
                    level=logging.INFO)

# Pull in the Excel Sheet with all the data we want -- See the CoMoChEng's Google Sheets spreadsheet
sheet = pandas.read_excel("imported_kinetic_modeling_metadata.xlsx")


def row_to_kinetic_model(row):
    """
    Takes a single row in the Sheet (represented by an index), strips its values, and saves a new Kinetic Model instance
    Integer -> KineticModel
    """
    # Test that the iterator is working
    logging.debug(get_row_value(row, 1))

    # Pull the values from the row in question to make a Dictionary of values
    kinetic_model_info = row_to_dict(row)

    # Make a new kinetic Model
    km = KineticModel()

    # Store the dictionary values in the Kinetic Model
    km.modelName = kinetic_model_info[u"Title"]

    # km.source = make_source()
    # mPrimeID = models.CharField('PrIMe ID', max_length=9, blank=True)
    # kinetics = models.ManyToManyField(Kinetics, through='KineticsComment',
    #                                   blank=True)
    # thermo = models.ManyToManyField(Thermo, through='ThermoComment',
    #                                 blank=True)
    # transport = models.ManyToManyField(Transport, blank=True)
    # additionalInfo = models.CharField(max_length=1000, blank=True)
    # #     reaction=kinetics something
    # #     species=reaction something
    # chemkinReactionsFile = models.FileField(upload_to=upload_chemkin_to, )
    # chemkinThermoFile = models.FileField(upload_to=upload_thermo_to, )
    # chemkinTransportFile = models.FileField(blank=True,
    #                                         upload_to=upload_transport_to, )

    # Lastly, save that instance
    # km.save()
    return km


# ----------------------------------------------------------------------------------------------------------------------


def row_to_dict(row):
    """
    Takes index of a Row  from the sheet (which contains info about a specific Kinetic Model) and converts it to a dict
    Integer -> Dictionary
    """
    global sheet
    dictionary = {}
    first_row = list(sheet)
    row_to_convert = sheet.iloc[row]
    for key in first_row:
        if key == "Port (next free=8174)":
            dictionary[u"Port"] = str(row_to_convert[key])
        else:
            dictionary[key] = str(row_to_convert[key])

    for key in dictionary:
        if dictionary[key] == "nan":
            dictionary[key] = ""

    return dictionary

# Test cases for row_to_dict
assert(row_to_dict(0) == {u"Authors": "Judit Zador, James A Miller",
                          u"DOI": "",
                          u"Identified Species": "",
                          u"Importing status?": "Broken",
                          u"Issue": "1.0",
                          u"Keywords": "Propanol; Master equation; Pressure-dependence; Formally direct; Alcohol",
                          u"Notes:": "Not a complete mechanism. Cant be imported",
                          u"PDF": "",
                          u"Pages ": "519-526",
                          u"Path": "PCI2013/519-Zador",
                          u"Port": "-",
                          u"Publication": "Proceedings of the Combustion Institute",
                          u"Reactions": "22",
                          u"Species Size": "7",
                          u"Symposium talk": "",
                          u"Title": "Unimolecular dissociation of hydroxypropyl and propoxy radicals",
                          u"Total Species": "",
                          u"Volume": "34.0",
                          u"Who got it": "Anthony",
                          u"Year": "2013.0"})


def get_row_value(row, column):
    """
    Given the Sheet of Kinetic Model info, pulls the value from the sheet given index for rows and columns
    Integer, Integer -> [String|Number|URL]
    """
    global sheet
    return sheet.iloc[row, column]

# Test cases for get_row_value
assert(get_row_value(0, 0) == "Unimolecular dissociation of hydroxypropyl and propoxy radicals")
assert(get_row_value(0, 1) == "Judit Zador, James A Miller")
assert(get_row_value(1, 0) == "Development of a new skeletal mechanism for n-decane oxidation under engine-relevant "
                              "conditions based on a decoupling methodology")
assert(get_row_value(1, 1) == "Yachao Chang, Ming Jia, Yaodong Liu, Yaopeng Li, Maozhao Xie")


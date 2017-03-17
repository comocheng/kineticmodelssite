#!/usr/bin/env python
# -*- coding: latin-1 -*-

import pandas
import logging
import os
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "rmgweb.settings")
django.setup()
from kineticmodels.models import Source, Author, Authorship


def row_to_source(row):  # TODO -- needs tests
    """
    Takes a single row in the Sheet (represented by an index), strips its values, and saves a new Kinetic Model instance
    Integer -> KineticModel
    """

    # Get the info we need from the Spreadsheet (DataFrame)
    source_info_dict = row_to_dict(row)

    # Make a new kinetic Model
    s = Source()

    # Store the dictionary values in the Kinetic Model
    s.publicationYear = source_info_dict[u"Year"][:4]
    s.sourceTitle = source_info_dict[u"Title"]
    s.journalName = source_info_dict[u"Publication"]
    s.journalVolumeNumber = source_info_dict[u"Volume"]
    s.pageNumbers = source_info_dict[u"Pages "]
    s.doi = source_info_dict[u"DOI"]

    # Save that instance
    # TODO IMPORTANT -- check that an identical Source doesn't already exist
    try:
        s.save()
        logging.info("Created the following Source Instance:\n{0}\n".format(s))
    except Exception, e:
        logging.error("Error saving the Source: {}".format(e))

    # Then create the Authorships
    if source_info_dict[u"Authors"] != "" and type(source_info_dict[u"Authors"]) in [str, unicode]:
        make_authorships(source_info_dict[u"Authors"], s)
    return s


def make_authorships(authors_str, source):
    """
    - Takes in a string of all the Author names
    - Parses the long string into a list of individual authors
    - Then for every individual author name:
        - Checks if the name already exists as an Author instance
            - If it doesn't, make a new Author
            - Then save that Author
        - Create an Authorship instance between the new Source and its Author
    -Returns all the Authorships somehow (or just saves them)
    String -> Authorships
    """

    # Local function definitions
    def authors_str_to_author_list(local_auth_str):
        """
        This function is a convenient place to put all the parsing that needs to be done on the author string;
        should the need ever arise to parse it differently just add another map_split_then_reduce
        String -> [Listof Strings]
        """

        # I know this is another Local but I swear it's for a good reason
        def map_split_then_reduce(input_l, split_str, max_split=None):
            """
            Applies a split to every String in a [Listof Strings],
            then reduces from a [List of Singleton-Lists] to a [Listof Strings]
            [Listof Strings] -> [Listof Strings]
            """
            return reduce(lambda base, val: base+val,
                          map(lambda item: item.split(split_str, max_split) if max_split
                              else item.split(split_str),
                              input_l),
                          [])

        # Makes the list by splitting the string the first time
        logging.debug(local_auth_str)
        local_auth_list = local_auth_str.split(", ")  # Include the space first to avoid spaces at beginning of names
        logging.debug("All good!")
        # Then splits every item in the list with the additional patterns
        local_auth_list = map_split_then_reduce(local_auth_list, ",")
        local_auth_list = map_split_then_reduce(local_auth_list, " and ")
        local_auth_list = map_split_then_reduce(local_auth_list, " ", max_split=1)  # Splits the first and last names...

        # ... and then puts the names back together
        # TODO -- This is kind of magical, see if there isn't some way to better document it or put it in a function
        local_auth_list = [local_auth_list[2*x+1]+", "+local_auth_list[2*x] for x in range(len(local_auth_list)/2)]

        return local_auth_list

    # Parses the long string into a list of individual authors
    authors_list = authors_str_to_author_list(authors_str)

    # Then for every individual author name:
    for index in range(len(authors_list)):
        # Checks if the name already exists as an Author instance
        author_object, created = Author.objects.get_or_create(name=authors_list[index])
        # If it doesn't, create/save an Author
        if created:
            logging.info("New Author object created for {}".format(author_object))
        else:
            logging.info("Exisitng Author object found for {}".format(author_object))

        # Create an Authorship instance between the new Source and its Author
        try:
            a = Authorship(author=author_object, source=source, order=int(index+1))
            a.save()
            logging.info("Authorship created: {}".format(a))
        except Exception, e:
            logging.error("Issue creating Authorship: {}".format(e))

    return True


def row_to_dict(row):
    """
    Takes index of a Row from the sheet (which contains info about a specific Kinetic Model) and converts it to a dict
    Integer -> Dictionary
    """

    # Local function definition
    def make_string_via_unicode(text):
        """
        Converts numbers and Unicode strings to normal Python strings.
        Allows us to avoid errors with str() that typically come up with NumPy Floats and Unicode Strings
        by turning the type into Unicode and then re-encoding it in ASCII
        """
        return unicode(text).encode('ascii', 'ignore')

    # Test cases for make_string_via_unicode
    assert (make_string_via_unicode(u"2013.0") == "2013.0")
    assert (make_string_via_unicode(2013.0) == "2013.0")

    # Main function code
    global sheet
    dictionary = {}
    first_row = list(sheet)
    row_to_convert = sheet.iloc[row]
    for key in first_row:
        if key == "Port (next free=8174)":  # Change to REGEX or .startswith
            dictionary[u"Port"] = make_string_via_unicode(row_to_convert[key])
        elif key == "Authors":
            dictionary[key] = row_to_convert[key]
        else:
            dictionary[key] = make_string_via_unicode(row_to_convert[key])

    for key in dictionary:
        if dictionary[key] == "nan":
            dictionary[key] = ""

    return dictionary


# MAIN FUNCTION CALL

if __name__ == "__main__":
    # Configure logging for debugging
    logging.basicConfig(filename="alpha_testing.log",
                        format="%(levelname)s: %(message)s",
                        level=logging.DEBUG)

    # Pull in the Excel Sheet with all the data we want -- See the CoMoChEng's Google Sheets spreadsheet
    sheet = pandas.read_excel("kineticmodels/ioscripts/imported_kinetic_modeling_metadata.xlsx")

    for line in range(len(sheet.index)):
        row_to_source(line)


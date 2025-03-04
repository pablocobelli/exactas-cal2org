#!/usr/bin/env python3

# Standard library imports
import re
import sys
from datetime import datetime

# Third-party imports
import yaml
import difflib
import requests
import dateparser
from bs4 import BeautifulSoup

# Get the script directory to locate calendar_headers_list.yaml file
script_dir = os.path.dirname(os.path.abspath(__file__))
HEADERS_FILE = os.path.join(script_dir, "calendar_headers_list.yaml")

# CONSTANTS
# URL of the Exactas academic calendar webpage
CALENDAR_URL = "https://exactas.uba.ar/calendario-academico/"
# # YAML file containing the calendar headers to extract
# HEADERS_FILE = "calendar_headers_list.yaml"

def strip_event_affixes(event_name):
    """
    Removes predefined prefixes and suffixes from an event name.

    This function trims specific prefixes and suffixes from the given
    event name, ensuring that the remaining string is clean. It also
    removes any extra whitespace that may result from the trimming.

    Parameters:
    event_name (str): The original event name.

    Returns:
    str: The cleaned event name without the specified prefixes and suffixes.
    """

    prefixes_list = ["Semana de"]
    suffixes_list = ["de cuatrimestre"]

    for prefix in prefixes_list:
        if event_name.startswith(prefix):
            event_name = event_name[len(prefix):].strip()
    for suffix in suffixes_list:
        if event_name.endswith(suffix):
            event_name = event_name[:-len(suffix)].strip()

    return event_name


def correct_month_name(month_input):
    """
    Corrects a possibly misspelled month name using approximate matches.

    This function takes a month name as input and finds the closest matching
    month from a predefined list of valid months using difflib's get_close_matches
    function. If the input is misspelled, it returns the closest month.

    Args:
        month_input (str): The name of the month to be corrected.

    Returns:
        list: A list containing the closest matching month found, or an empty list
              if no close match is found.
    """
    months = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
             "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
    matches = difflib.get_close_matches(month_input, months, n=1)

    return matches[0]


def correct_day_name(dayname_input):
    """
    Corrects a possibly misspelled day name using approximate matches.

    This function takes a day name as input and finds the closest matching
    day from a predefined list of valid days using difflib's get_close_matches
    function. If the input is misspelled, it returns the closest day.

    Args:
        dayname_input (str): The name of the day to be corrected.

    Returns:
        list: A list containing the closest matching day found, or an empty list
              if no close match is found.
    """
    days = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
    matches = difflib.get_close_matches(dayname_input, days, n=1)

    return matches[0]


def get_date_or_timeframe(section_text):
    """
    Extracts a date or a date range from a given section of text.

    This function searches for a single date or a date range using predefined regex patterns.
    It prioritizes matches as follows:
        1. A single date (e.g., "lunes 15 de marzo")
        2. A date range within the same month (e.g., "lunes 10 al viernes 15 de marzo")
        3. A date range spanning different months (e.g., "lunes 10 de marzo al martes 28 de abril")

    If multiple matches are found, the highest-priority match is returned.

    Args:
        section_text (str): The input text containing a potential date or timeframe.

    Returns:
        tuple:
            - list: A list containing the extracted date(s).
            - bool: True if a single date was found, False if a date range was found.

    Notes:
        - If a range within the same month is found, the month name is appended to the first date for clarity.
        - If no match is found, the function prints a failure message and `out` remains undefined.
    """

    # Regex para las fechas posibles
    regex_fecha_unica = r"(\w+ \d{1,2} de \w+)"  # Una sola fecha
    regex_plazo_mismo_mes = r"(\w+ \d{1,2}) al (\w+ \d{1,2} de \w+)"  # Plazo en el mismo mes
    regex_plazo_diferente_mes = r"(\w+ \d{1,2} de \w+) al (\w+ \d{1,2} de \w+)"  # Plazo en diferentes meses

    # Lista de regex con un orden de prioridad
    regex_list = [
        (regex_fecha_unica, 3),  # Prioridad 1: Solo una fecha
        (regex_plazo_mismo_mes, 2),  # Prioridad 2: Plazo en el mismo mes
        (regex_plazo_diferente_mes, 1)  # Prioridad 3: Plazo en diferentes meses
    ]

    # Lista para almacenar las coincidencias encontradas
    matches = []

    # Intentamos cada regex en el orden de la lista
    for regex, priority in regex_list:
        coincidence = re.search(regex, section_text)
        if coincidence:
            if len(coincidence.groups()) == 1:
                # Solo una fecha
                date = coincidence.group(1)
                matches.append((date, priority))
            else:
                # Es un plazo
                starting_date = coincidence.group(1)
                ending_date = coincidence.group(2)
                matches.append((starting_date, ending_date, priority))

    # Si encontramos coincidencias, las ordenamos por prioridad
    if matches:
        matches.sort(key=lambda x: x[-1])  # Ordenamos por el último elemento de las tuplas (priority)
        # Retornamos la coincidencia de mayor prioridad
        if len(matches[0]) == 2:
            out = [matches[0][0]]
            single_date_boolean = True
        else:
            if matches[0][2] == 2:
                # same month, get it from second part
                last_two_words = " ".join(matches[0][1].split()[-2:])
                out = [matches[0][0] + " " + last_two_words, matches[0][1]]
            else:
                out = [matches[0][0], matches[0][1]]
            single_date_boolean = False
    else:
        # Si no encontramos ninguna coincidencia
        print('Failed to find date or period in string.')

    return out, single_date_boolean


def read_html_source_from_url(url):
    """
    Fetches and parses the HTML content from the given URL.

    This function sends an HTTP GET request to the specified URL, checks for
    request errors, and returns a BeautifulSoup object for further HTML parsing.

    Parameters:
        url (str): The URL of the webpage to fetch.

    Returns:
        BeautifulSoup: A parsed BeautifulSoup object containing the page's HTML structure.

    Raises:
        requests.exceptions.RequestException: If the request fails (e.g., network issues,
                                              invalid URL, or server error).
    """
    response = requests.get(url)
    # Verify that the request was successful
    response.raise_for_status()

    # Parse the HTML content of the page
    soup = BeautifulSoup(response.text, "html.parser")
    return soup


def get_section_lines(soup, target_header):
    """
    Extracts text from a section identified by a specific header.

    This function searches for a header tag (h1–h6) whose text starts with `target_header`
    and retrieves all text from its section, stopping at the next header of the same or
    higher level.

    Parameters:
        soup (BeautifulSoup): The parsed HTML document.
        target_header (str): The title of the section to extract.

    Returns:
        list[str]: A list of strings, where each string is a line of text from the section.

    Raises:
        AttributeError: If no matching header is found in the document.
    """

    header_list = ["h1", "h2", "h3", "h4", "h5", "h6"]
    header = soup.find(lambda tag: tag.name in header_list and tag.text.startswith(target_header))

    section_text = []

    # Traverse elements until the next header of the same or higher level
    for sibling in header.find_next_siblings():
        if sibling.name in header_list:
            break  # Stop at the next header

        lines_of_text = sibling.get_text(strip=True, separator="\n").split("\n")
        section_text.extend(lines_of_text)

    return section_text


def read_event_list_from_yaml(yaml_file):
    """
    Reads a list of required events from a YAML file.

    This function opens the specified file, reads its contents line by line,
    and returns a list where each line is an event.

    Parameters:
        file (str): The path to the file containing the event list.

    Returns:
        list[str]: A list of strings, where each string represents an event.

    Raises:
        FileNotFoundError: If the file does not exist.
        UnicodeDecodeError: If the file encoding is not compatible with UTF-8.
    """

    # Leer el archivo YAML
    with open(yaml_file, "r", encoding="utf-8") as file:
        required_events = yaml.safe_load(file)

    return required_events


def normalize_event_casing(event_name):
    """
    This function converts the event name to lowercase and then capitalizes
    the first letter, ensuring a consistent formatting style.

    Parameters:
    event_name (str): The original event name.

    Returns:
    str: The event name with normalized casing.

    Example:
    >>> normalize_event_casing("WEEKEND FESTIVAL")
    'Weekend festival'
    >>> normalize_event_casing("science Fair")
    'Science fair'
    """
    return event_name.lower().capitalize()


def parse_date_from_string(date_in_text_format):
    """
    Parses a date from a text string and converts it to a standardized date format.

    This function extracts a date from a given string using a predefined regex pattern.
    It corrects any typos in the day name and month name before reconstructing the date
    in natural language and converting it to a universal date format.

    Args:
        date_in_text_format (str): A date string in the format "dayname daynumber de monthname"
                                   (e.g., "lunes 15 de marzo").

    Returns:
        datetime.date: The parsed date in a universal format (YYYY-MM-DD).

    Notes:
        - The function assumes that the input string contains a valid date in Spanish.
        - It uses `correct_day_name` and `correct_month_name` to fix potential typos.
        - The final date is parsed using `dateparser.parse` and returned in the standard date format.
    """
    regex_date = r"(\w+) (\d{1,2}) de (\w+)"

    # separate each part of the date expression in natural language
    coincidence = re.search(regex_date, date_in_text_format)
    dayname, daynumber, monthname = coincidence.groups()

    # correct typos in dayname and monthname
    dayname = correct_day_name(dayname)
    monthname = correct_month_name(monthname)

    # regenerate date in natural language with corrected typos (if any)
    date_in_natural_language = " ".join([dayname, daynumber, monthname])
    # convert to universal format
    date_in_universal_format = dateparser.parse(date_in_natural_language).date()

    return date_in_universal_format


def create_org_from_calendar_headers(soup, cal_headers):
    """
    Extracts events from calendar headers and formats them as an Org-mode file structure,
    for use with org-agenda.

    This function processes event data from a parsed HTML document, extracts relevant sections
    based on calendar headers, and converts them into a structured Org-mode format.

    Args:
        soup (BeautifulSoup): The parsed HTML document containing the event data.
        cal_headers (dict): A dictionary where keys are full calendar section names and values
                            are their short names for Org-mode formatting.

    Outputs:
        - Prints an Org-mode structured outline of the extracted events, formatted as follows:
            * <Current Year>
            ** <Calendar Header>
            *** <Short Name> <Event Name> (optional suffix for multiple exam dates)
                <Formatted Date>  (or a date range in Org-mode syntax)

    Processing Steps:
        1. Prints the current year as the top-level heading.
        2. Iterates through the provided calendar headers:
           - Extracts section text using `get_section_lines()`.
           - Identifies specific exam dates ("Primera fecha", "Segunda fecha", etc.).
           - Splits event lines into event names and their corresponding dates.
           - Determines if the event has a single date or a timeframe.
           - Parses the date(s) using `parse_date_from_string()`.
           - Normalizes event name formatting with `normalize_event_casing()`.
           - Prints the event as an Org-mode entry.

    Notes:
        - Single dates are formatted as `<YYYY-MM-DD Day>`.
        - Date ranges are formatted as `<YYYY-MM-DD Day>-<YYYY-MM-DD Day>`.
        - Event names are cleaned up using `strip_event_affixes()` and `normalize_event_casing()`.
        - Multiple exam dates (e.g., first, second, third) are annotated accordingly.

    Example Org-mode Output:
        * 2025
        ** Final Exams
        *** Finals Math (1ra fecha)
            <2025-06-15 Sun>
        *** Finals Physics
            <2025-07-01 Tue>-<2025-07-05 Sat>

    """

    current_year = str(datetime.now().year)
    print("* " + current_year)

    for cal_header, cal_header_short_name in cal_headers.items():
        print("** " + cal_header)
        section_text = get_section_lines(soup, cal_header)
        extra_suffix_for_multiple_exam_dates = ''
        for line in section_text:
            if "Primera fecha" in line:
                extra_suffix_for_multiple_exam_dates = " (1ra fecha)"
            elif "Segunda fecha" in line:
                extra_suffix_for_multiple_exam_dates = " (2da fecha)"
            elif "Tercera fecha" in line:
                extra_suffix_for_multiple_exam_dates = " (3ra fecha)"
            else:
                # Conversion to ORG-MODE FORMAT
                event_name, event_date_or_timeframe = line.split(':')
                date_or_timeframe, is_single_date = get_date_or_timeframe(event_date_or_timeframe)
                if is_single_date:
                    # it is just a simple date
                    date_for_event = parse_date_from_string(date_or_timeframe[0])
                    formatted_date_for_event = date_for_event.strftime("<%Y-%m-%d %a>")
                    event_name = normalize_event_casing(event_name)
                    print("*** " + cal_header_short_name + " " + event_name +
                        extra_suffix_for_multiple_exam_dates)
                    print(formatted_date_for_event)
                else:
                    # it is a timeframe (two dates: start and end)
                    period = []
                    for each_date in date_or_timeframe:
                        date_for_event = parse_date_from_string(each_date)
                        formatted_date_for_event = date_for_event.strftime("<%Y-%m-%d %a>")
                        period.append(formatted_date_for_event)
                    # Join both dates (start and end) with "-" for ORG-MODE
                    period = "-".join(period)
                    event_name = strip_event_affixes(event_name)
                    # Hagamoslo lowercase, luego capitalizamos la primera letra
                    event_name = normalize_event_casing(event_name)
                    print("*** " + cal_header_short_name + " " + event_name +
                        extra_suffix_for_multiple_exam_dates)
                    print(period)


def main():
    """Fetch the academic calendar, extract events, and print them in Org-mode format."""

    # Fetch and parse the HTML source using BeautifulSoup
    soup = read_html_source_from_url(CALENDAR_URL)
    if soup is None:
        # display error message and return error code (1)
        print("Error: Failed to fetch the webpage.", file=sys.stderr)
        return 1

    # Load the list of calendar headers from the YAML file
    cal_headers = read_event_list_from_yaml(HEADERS_FILE)
    if not cal_headers:
        # display error message and return error code (1)
        print("Error: No calendar headers found in the YAML file.", file=sys.stderr)
        return 1

    # Process each calendar section based on the given headers,
    # extract events, and print them line by line in Org-mode format
    # for their use with org-agenda
    create_org_from_calendar_headers(soup, cal_headers)

    return 0


if __name__ == '__main__':
    sys.exit(main())

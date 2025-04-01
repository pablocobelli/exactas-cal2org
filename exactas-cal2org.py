#!/usr/bin/env python3

# Standard library imports
import os
import re
import sys
from datetime import datetime

# Third-party imports
import yaml
import difflib
import requests
import dateparser
from bs4 import BeautifulSoup

# CONSTANTS
YAML_FILE = "calendar_headers_list.yaml"
CALENDAR_URL = "https://exactas.uba.ar/calendario-academico/"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
HEADERS_FILE = os.path.join(SCRIPT_DIR, YAML_FILE)

CURRENT_YEAR = datetime.now().year
DAYS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
MONTHS_DICT = {
    "enero": "01", "febrero": "02", "marzo": "03", "abril": "04", "mayo": "05", "junio": "06",
    "julio": "07", "agosto": "08", "septiembre": "09", "octubre": "10", "noviembre": "11", "diciembre": "12"
}

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
    months = list(MONTHS_DICT.keys())
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
    matches = difflib.get_close_matches(dayname_input, DAYS, n=1)

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

    # Regex for detecting possible date formats
    regex_fecha_unica = r"(\w+ \d{1,2} de \w+)"  # Just one date
    regex_plazo_mismo_mes = r"(\w+ \d{1,2}) al (\w+ \d{1,2} de \w+)"  # Multiple days in same month
    regex_plazo_diferente_mes = r"(\w+ \d{1,2} de \w+) al (\w+ \d{1,2} de \w+)"  # Multiple days in different months

    # Regex list with a priority order
    regex_list = [
        (regex_fecha_unica, 3),  # Priority 1: just one date
        (regex_plazo_mismo_mes, 2),  # Priority 2: multiple days in same month
        (regex_plazo_diferente_mes, 1)  # Priority 3: multiple days in different months
    ]

    # List to store found matches
    matches = []

    # Each regex is tried in the list's order
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

    # If matches found, order them by priority
    if matches:
        matches.sort(key=lambda x: x[-1])  # Ordering by last element in the tuples (i.e., priority)
        # Return match with highest priority
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
        # If no matches are found
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

    # Read YAML file
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

def create_org_contents_from_calendar_headers(soup, cal_headers):
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

    print("* " + str(CURRENT_YEAR))
    print("** FECHAS DE CURSADA Y DE FINALES")

    for cal_header, cal_header_short_name in cal_headers.items():
        print("*** " + cal_header)
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
                    print("**** " + cal_header_short_name + " " + event_name +
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
                    print("**** " + cal_header_short_name + " " + event_name +
                        extra_suffix_for_multiple_exam_dates)
                    print(period)

def get_events_from_yaml_file():

    # Load the list of calendar headers from the YAML file
    all_headers = read_event_list_from_yaml(HEADERS_FILE)

    main_header_cursada = "FECHAS DE CURSADA Y DE FINALES"
    main_header_feriados = "FERIADOS"
    main_header_semanas = "SEMANAS DE LAS CIENCIAS"

    if main_header_cursada in all_headers:
        headers_cursada = all_headers["FECHAS DE CURSADA Y DE FINALES"]
    else:
        headers_cursada = None

    if main_header_feriados in all_headers:
        include_holidays = True
    else:
        include_holidays = None

    if main_header_semanas in all_headers:
        headers_semanas = all_headers["SEMANAS DE LAS CIENCIAS"]
    else:
        headers_semanas = None

    return headers_cursada, headers_semanas, include_holidays


def main():
    """Fetch the academic calendar, extract events, and print them in Org-mode format."""

    # Fetch and parse the HTML source using BeautifulSoup
    soup = read_html_source_from_url(CALENDAR_URL)
    if soup is None:
        # display error message and return error code (1)
        print("Error: Failed to fetch the webpage.", file=sys.stderr)
        return 1

    # Separate each calendar section based on the given headers
    # by one of the three types of header: cursada, semanas, feriados
    headers_cursada, headers_semanas, include_holidays = get_events_from_yaml_file()

    if headers_cursada is not None:
        create_org_contents_from_calendar_headers(soup, headers_cursada)
    if include_holidays is not None:
        create_org_contents_from_holidays_header(soup)
    if headers_semanas is not None:
        create_org_contents_from_science_weeks_header(soup)

    return 0

def create_org_contents_from_holidays_header(soup):
    # Holidays are listed in the last table of the website
    holidays_table = soup.find_all("table")[-1]

    output_text = "** FERIADOS\n"

    # Iterate over all table rows
    for row in holidays_table.find_all("tr"):
        # Extract all (td) cells from row
        cells = row.find_all("td")
        if cells:  # Verify there are cells in the row
            # Extract the text of each cell, stripping white space and correcting for possible typos
            day_name = cells[0].get_text(strip=True)
            day_name = correct_day_name(day_name)
            date_in_text_format = cells[1].get_text(strip=True)
            event = cells[2].get_text(strip=True)
            condition = cells[3].get_text(strip=True)
            if not condition:
                condition = "No especificada en el sitio web"

            # We convert date_in_text_format (e.g., 23 de abril) to "YYYY-MM-DD" format
            try:
                day_number, month_name = [x.strip() for x in date_in_text_format.split("de")]
                month_name = correct_month_name(month_name)
                month_number = MONTHS_DICT[month_name.lower()]
                formatted_date_for_heading = f"{CURRENT_YEAR}-{month_number}-{day_number.zfill(2)}"
            except (ValueError, KeyError):
                formatted_date_for_heading = "Fecha inválida"

            # Build the holiday entry for current line in table
            output_text += f"*** Feriado: {event} ({day_name} {day_number} de {month_name})\n"
            output_text += f"<{formatted_date_for_heading}>\n"
            output_text += f"Condición: {condition}.\n"

    # Print the holidays section
    print(output_text)
    return None


def add_entries_for_science_week(soup, science_week_name):

    output_text = ""

    tag = soup.find("strong", string=science_week_name)

    if tag:
        # Get next sibling containing the text following the match
        science_week_dates_in_text_format = tag.find_next_sibling(string=True)  # Using 'string=True' to get only the text
        if science_week_dates_in_text_format:
            # Clean up text and separate dates (3 days)
            science_week_dates_in_text_format = science_week_dates_in_text_format.strip()

            for month in MONTHS_DICT:
                if month in science_week_dates_in_text_format.lower():
                    # Get the month number
                    month_number = MONTHS_DICT[month]
                    # Extract only days using regex
                    days = re.findall(r'\d+', science_week_dates_in_text_format.split(month)[0])

                    # Build a list of dates in YYYY-MM-DD format
                    dates = []
                    for day in days:
                        date = datetime(CURRENT_YEAR, int(month_number), int(day)).date()
                        dates.append(date.strftime('%Y-%m-%d'))

                    output_text += f"*** {science_week_name}\n"
                    output_text += f"<{dates[0]}>-<{dates[2]}>"
                    break
            else:
                print("Mes no encontrado en el texto.")
        else:
            print("No se encontró la fecha después del texto buscado.")
    else:
        print("Texto no encontrado en la página.")

    print(output_text)
    return None

def create_org_contents_from_science_weeks_header(soup):
    # These entries could be read from the YAML
    print("** SEMANAS DE LAS CIENCIAS")
    add_entries_for_science_week(soup, "Semana de la Matemática y de las Ciencias de Datos")
    add_entries_for_science_week(soup, "Semana de las Ciencias de la Tierra")
    add_entries_for_science_week(soup, "Semana de la Física")
    add_entries_for_science_week(soup, "Semana de la Computación y de las Ciencias de Datos")
    add_entries_for_science_week(soup, "Semana de la Biología")
    add_entries_for_science_week(soup, "Semana de la Química y de los Alimentos")
    add_entries_for_science_week(soup, "Semana de la Enseñanza de las Ciencias")
    return None

if __name__ == '__main__':
    sys.exit(main())

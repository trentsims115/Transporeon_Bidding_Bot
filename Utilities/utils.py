"""This module includes all utility functions that are used by the bot"""
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.common.exceptions import StaleElementReferenceException
from Utilities.pia import switch_region
import datetime
import math
import time
import zipcodes
import re


refresh_count = 0
active_driver = 1

def convert_date_string(date_string):
    """
    Converts a date string in the format 'dd-Mon-yy hh:mm AM/PM TZ' to 'YYYY-MM-DD' format.
        Args: date_string (str): The date string to convert.
        Returns: str: The converted date in 'YYYY-MM-DD' format.
    """
    if date_string == '':
        return ''
    parsed_date = datetime.datetime.strptime(date_string, "%m/%d/%Y %H:%M")

    # Format the date as "YYYY-MM-DD"
    formatted_date = parsed_date.strftime("%Y-%m-%d")

    return formatted_date

def web_driver_wait_by_xpath(driver, wait_time, xpath):
    """
    This functions finds an element by the time specified
        driver: driver from selenium to use
        wait_time: amount of time to wait for element to appear
        xpath: The xpath of the element to wait on
        Return: returns a pointer to the specified HTML element
    """
    return WebDriverWait(driver, wait_time).until(
        EC.presence_of_element_located((By.XPATH, xpath))
    )

def calculate_days_in_future(date_string):
    """
    Calculates the number of days in the future from today to a given date.
        date_string (str): A string representing the future date in the format "YYYY-MM-DD" or "YYYY/M/D".
        Return: the number of days in the future from today to the given date.
    """
    if date_string == '':
        return ''
    if "/" in date_string:
        future_date = datetime.datetime.strptime(date_string, "%Y/%m/%d").date()
    else:
        future_date = datetime.datetime.strptime(date_string, "%Y-%m-%d").date()
    today = datetime.datetime.today().date()
    days_in_future = (future_date - today).days
    return days_in_future

def current_day_of_week():
    """returns the current day of the week using numerical values 0-6 || 0 = Monday"""
    return datetime.date.today().weekday()

def check_day():
    """Returns the current day in this format: 2023-01-25"""
    day_and_time = datetime.datetime.fromtimestamp(time.time()).strftime('%Y-%m-%d')
    return str(day_and_time)

def check_time():
    """Returns the current time in this format: %H: %M: %S - 01:05:32"""
    day_and_time = datetime.datetime.fromtimestamp(time.time()).strftime('%H:%M:%S')
    return str(day_and_time)

def time_now():
    """
    Gets the current time and day of week in this format: %Y-%m-%d %H:%M:%S - 2023-06-25 12:32:33
    """
    # Get the current date and time
    current_datetime = datetime.datetime.now()

    # Convert the datetime object to a string in SQL-compatible format
    sql_datetime = current_datetime.strftime("%Y-%m-%d %H:%M:%S")

    return sql_datetime

def get_date_with_offset(day_offset):
    """
    Gets the date -/+ the amount of days you describe
        day_offset: how many days off from today do you want the date
        Return: 2023-07-15
    """
    today = datetime.datetime.today()
    tomorrow = today + (day_offset*datetime.timedelta(days=1))
    return tomorrow.strftime("%Y-%m-%d")

def save_page_source(driver, filename, folder_name='../acceptPageHTML'):
    import os
    # Create folder if it doesn't exist
    if not os.path.exists(folder_name):
        os.makedirs(folder_name)

    # Get the current timestamp
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

    # Create a file name with the timestamp
    file_name = f'{filename}_{timestamp}.html'

    # Get the page source
    page_source = driver.page_source

    # Create the full path for the file
    file_path = os.path.join(folder_name, file_name)

    # Write the page source to the file
    with open(file_path, 'w', encoding='utf-8') as file:
        file.write(page_source)

    print(f"Page source saved to {file_path}")

def round_to_increment(value, increment, direction="nearest"):
    """
    Rounds a numeric value to a given increment in a specified direction.

    Args:
        value (float): The number to round.
        increment (float): The step size to round to (e.g., 0.05, 10, 0.25).
        direction (str): One of 'up', 'down', or 'nearest'.

    Returns:
        float: The rounded value.
    """
    if increment == 0:
        raise ValueError("Increment cannot be zero.")
    if direction not in {"up", "down", "nearest"}:
        raise ValueError("Direction must be 'up', 'down', or 'nearest'.")

    factor = value / increment

    if direction == "up":
        rounded = math.ceil(factor) * increment
    elif direction == "down":
        rounded = math.floor(factor) * increment
    else:  # "nearest"
        rounded = round(factor) * increment

    # Avoid floating-point artifacts like 2.4000000000000004
    return round(rounded, len(str(increment).split('.')[-1]) if '.' in str(increment) else 0)

def save_page_source(driver, filename, folder_name='./Logs/Page_Sources'):
    import os
    # Create folder if it doesn't exist
    if not os.path.exists(folder_name):
        os.makedirs(folder_name)

    # Get the current timestamp
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

    # Create a file name with the timestamp
    file_name = f'{filename}_{timestamp}.html'

    # Get the page source
    page_source = driver.page_source

    # Create the full path for the file
    file_path = os.path.join(folder_name, file_name)

    # Write the page source to the file
    with open(file_path, 'w', encoding='utf-8') as file:
        file.write(page_source)

    print(f"Page source saved to {file_path}")



def save_screenshot(driver, filename, folder_name='./Logs/Screenshots'):
    import os
    # Create folder if it doesn't exist
    if not os.path.exists(folder_name):
        os.makedirs(folder_name)

    # Get the current timestamp
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

    # Create a file name with the timestamp
    file_name = f'{filename}_{timestamp}.png'

    # Create the full path for the file
    file_path = os.path.join(folder_name, file_name)

    # Save the screenshot
    driver.save_screenshot(file_path)

    print(f"Screenshot saved to {file_path}")

def get_state(zipcode: str) -> str | None:
    rec = zipcodes.matching(zipcode)[0]    # or .filter_by(city="Decatur", state="AL")
    print(rec['state'])
    return rec['state']

def wait_text_by_xpath(driver, wait_time, xpath):
    """
    Wait for an element located by xpath and return its text,
    retrying automatically if the element goes stale.
    """
    attempts = 3
    last_exc = None
    for _ in range(attempts):
        try:
            el = WebDriverWait(
                driver,
                wait_time,
                ignored_exceptions=(StaleElementReferenceException,)
            ).until(EC.presence_of_element_located((By.XPATH, xpath)))
            return el.text
        except StaleElementReferenceException as e:
            last_exc = e
            continue
    # if we get here, all retries failed
    raise last_exc

def normalize_country(country: str) -> str:
    """
    Normalize a variety of country inputs to one of:
    'USA', 'Canada', or 'Mexico'.

    Returns None if the country cannot be determined.
    """

    if not country:
        return None

    # Normalize basic formatting
    c = country.strip().lower()
    c = re.sub(r'[^a-z]', '', c)  # remove punctuation like ., -, spaces

    # --- USA Variants ---
    usa_aliases = {
        "us", "usa", "u", "unitedstates", "unitedstatesofamerica",
        "amer", "america", "states"
    }

    # --- Canada Variants ---
    canada_aliases = {
        "ca", "can", "cdn", "canada", "cda"
    }

    # --- Mexico Variants ---
    mexico_aliases = {
        "mx", "mex", "mexico", "mxn"
    }

    if c in usa_aliases:
        return "USA"
    if c in canada_aliases:
        return "Canada"
    if c in mexico_aliases:
        return "Mexico"

    return None

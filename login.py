from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from Utilities.utils import web_driver_wait_by_xpath
import time
from Utilities.countdown import countdown


def login(driver, user, password, website):
    """
    This function will log in with the given url and user account info
        driver: driver from selenium to use
        account: Account ot log in with
        user: user name for the loadboard
        password: password for the loadboard
        website: the website to log in to
    """
    driver.get(website)
    time.sleep(10)
    web_driver_wait_by_xpath(driver, 5, "//*[@id='emailForm_email-input']").send_keys(user)
    web_driver_wait_by_xpath(driver, 5, "//*[@id='emailForm_password-input']").send_keys(password)
    web_driver_wait_by_xpath(driver, 5, "//*[@id='emailForm_submit']/div").click()
    countdown(3)
    driver.maximize_window()
    countdown(10)

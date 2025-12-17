from login import login
from _bot import _bot
import traceback
from seleniumwire import webdriver            # type: ignore # <--- use selenium-wire's webdriver
from selenium.webdriver.edge.options import Options
from selenium.webdriver.edge.service import Service
from selenium.webdriver.edge.options import Options as EdgeOptions
from selenium.webdriver.edge.service import Service as EdgeService
from Utilities.email import send_login_failure_email
from Utilities.logger_config import logger
from Utilities.call_eia import get_surcharge_per_mile
from Utilities import storage
from Utilities.bot_functions import should_run_now
import threading
from server import start_api_server
import time
# from server import app

# def run_flask_app():
#     app.run(host='0.0.0.0', port=8001)  # Set use_reloader=False to prevent the app from running twice

def start_controller_thread():
        t = threading.Thread(target=start_api_server, kwargs={"host": "0.0.0.0", "port": 8001}, daemon=True)
        t.start()
        return t

if __name__ == "__main__":
    """Main bot program runs here. First it will login and then run main bot"""
    # Start Flask server in separate thread
    # flask_thread = threading.Thread(target=run_flask_app)
    # flask_thread.start()
    logger.info("Bot Starting")

    # Path to the manually downloaded EdgeDriver
    # driver_path = "C:\\Bots\\New_Carrier_Point_Bot\\msedgedriver.exe"

    # Create EdgeOptions object for both drivers
    opts = EdgeOptions()
    opts.add_argument('log-level=3')
    opts.use_chromium = True
    opts.add_argument("--disable-extensions")
    opts.add_argument("--disable-features=EnableAutologin")
    opts.set_capability("goog:loggingPrefs", {"performance": "ALL"})
    opts.set_capability("ms:loggingPrefs",   {"performance": "ALL"})
    # options1.add_argument("--proxy-server=http://127.0.0.1:8888")

    login_counter = 0
    bot_reset_counter = 0

    # Get account credentials from database
    user = storage.user_data[2]
    password = storage.user_data[3]
    website = storage.user_data[0]

    controller_thread = start_controller_thread()
    

    # Main driver loop
    while True:
        if not should_run_now():
             time.sleep(60 * 30)
        # Use selenium-wire's Edge webdriver (so requests/responses are intercepted)
        driver = webdriver.Edge(service=EdgeService(log_output="msedgedriver.log", verbose=True), options=opts)

        print("Browser:", driver.capabilities.get("browserName"), driver.capabilities.get("browserVersion"))
        print("EdgeDriver:", (driver.capabilities.get("msedge") or {}).get("msedgedriverVersion"))
        driver.execute_cdp_cmd("Network.enable", {})
        print("Available log types:", driver.log_types)
        try:
            print("logging in")
            login(driver, user, password, website)
            login_counter = 0
        except Exception as e:
                login_counter += 1
                logger.error(f"The following error occured when trying to login: {e}", exc_info=True)
                print("Failed logging in. Trying again.\nCurrent login count: " + str(login_counter))
                driver.quit()
                if login_counter == 3:
                    send_login_failure_email(['becca.romas@paulinc.com', 'Trenton.Sims@paulinc.com'], storage.load_board)
                    break
                continue
        try:
            logger.info("Bot Starting")
            _bot(driver)
            logger.info("Bot restarted")
            try:
                storage.load_data()
            except:
                 print("Unable to load data from database!")
                 logger.error("Cannot load data from database")
        except Exception as e:
            print('The bot has run into an error! Resetting and retrying.\n Current Retry Count: ' + str(bot_reset_counter))
            print(e)

            # Print line number and file
            tb = traceback.extract_tb(e.__traceback__)[-1]  # last frame
            print(f"Error occurred in file: {tb.filename}, line: {tb.lineno}")

            logger.error(f"The following error occurred when the bot was running: {e}", exc_info=True)
            bot_reset_counter += 1
        driver.quit()

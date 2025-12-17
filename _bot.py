"""This module contains the main bot functionality"""
from Utilities.utils import web_driver_wait_by_xpath, current_day_of_week, save_page_source, save_screenshot
from Utilities.make_dat_call import make_dat_call
from check_restriction import check_lane_restrictons
from Utilities.email import send_linehaul_load_found_email
from Utilities.bot_functions import get_latest_network_call, navigate_to_bid_screen, refresh_page, get_total_loads, iteration_actions, get_load_information, handle_load_error, bid_load, reject_load, handle_evraz_condition
from Utilities.logger_config import logger
from Utilities.countdown import countdown
from Utilities import storage
import time
import math
import json, gzip

def _bot(driver):
    """This is the main bot. Once logged in, this function gets called to iterate over the load board and select and grab each load that matches the rules. Switches between two drivers"""
    # Go to the tender page and check for total load.
    load_list_results = []
    error_count = 0
    refresh_count = 0
    active_driver = 1
    max_results_per_page = 75
    which_board = 0
    day_of_week = current_day_of_week()
    while True:
        sleep_counter = 0
        if storage.config["on"] == 0:
            countdown(120)
            sleep_counter += 120
            continue
        if sleep_counter >= (60 * 60):
            return
        refresh_page(driver)
        if iteration_actions(day_of_week):
            return
        # Load Board (Line Haul) XPath: //*[@id="right"]/div/div[2]/nav/ul/tmx-expansion-panel/li/a/span[2] and text must = 'Load Board'
        # Attempt to get total number of loads. If it fails, it usually means the website had an issue
        countdown(5)
        # network_name = "dispatch"
        # result = get_latest_network_call(driver, network_name)
        total_number_load_results = get_total_loads(driver)
        # If no loads, then reload the page
        # if total_number_load_results == 0:
        #     print('No loads found. Refreshing page')
        #     continue
        # else:
        #     total_number_load_results = len(result)
        # get total number of pages
        # number_of_pages = math.ceil(total_number_load_results / max_results_per_page) or 1
        # Get every load on list and store any relevant information.
        for j in range(total_number_load_results):
            load = {}
            load = get_load_information(driver, load_list_results, j)
            if load == {}:
                continue
            print(load)
            load_list_results.append(load)
            dat_data = make_dat_call(load)
            print(dat_data)
            # dat_data_90_day = make_dat_call(load, "average")
            load['dat_response'] = dat_data['response']['rateResponses'][0]['response']
            load['est_distance'] = dat_data['response']['rateResponses'][0]['response']['rate']['mileage']
            print(dat_data['response']['rateResponses'][0]['response']['rate']['perTrip']['rateUsd'])
            print(dat_data['response']['rateResponses'][0]['response']['rate']['averageFuelSurchargePerTripUsd'])
            base_rate = dat_data['response']['rateResponses'][0]['response']['rate']['perTrip']['rateUsd']
            load['quote_id'] = dat_data['response']['transaction']
            base_rate += dat_data['response']['rateResponses'][0]['response']['rate']['averageFuelSurchargePerTripUsd']
            load['bid_failure_reason'] = ''
            restrictions_check = check_lane_restrictons(load, base_rate)
            print(restrictions_check)
            print(load['reason'])
            if restrictions_check[0]:
                load['bid_recommended'] = 1
            load['amount'] = restrictions_check[1]
            load['base_rate'] = base_rate
            if restrictions_check[0]:
                if not storage.config["bidding"]:
                    storage.save_load_to_db(load)
                    storage.load_data()
                    print("Bot is in no bid mode")
                    continue
                # Put code here that will accept a load
                if bid_load(driver, load, j, restrictions_check[1]):
                    continue
                break
            reject_load(driver, load)


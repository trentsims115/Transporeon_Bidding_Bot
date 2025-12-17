import datetime
import re
import time
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException

refresh_count = 0
active_driver = 1


def iteration_actions(day_of_week):
    from Utilities import iteration_counter
    from Utilities.utils import current_day_of_week, time_now
    from Utilities.pia import switch_region
    from Utilities import storage

    print(time_now())
    print("Checking for new loads")
    iteration_counter.inc()
    curr_time = datetime.datetime.now()
    # Check if the current hour is divisible by 2 and the minutes are 0 (e.g., 2:00, 4:00, etc.)
    if curr_time.minute == 0 and curr_time.hour % 2 == 0:
        print(f"It's {curr_time.strftime('%I:%M %p')}. The bot is restarting")
        # If additional action is needed before restart, include it here. For example:
        # switch_region()
        return True  # Indicate that the bot should restart
    if day_of_week != current_day_of_week():
        day_of_week = current_day_of_week()
        iteration_counter.set(0)
        return True # Indicates that the bot should restart
    return not should_run_now()

def should_run_now():
    """
    Checks current time and day against storage.config["schedule"].
    Returns True if bot should be running now, False otherwise.
    """
    from Utilities import storage
    import pytz
    from datetime import datetime, time
    sched = storage.config.get("schedule", {})
    if not sched or not sched.get("enabled"):
        return True  # no schedule means always allowed to run

    tz_name = sched.get("timezone") or "America/Chicago"
    try:
        tz = pytz.timezone(tz_name)
    except Exception:
        tz = pytz.timezone("America/Chicago")

    now = datetime.now(tz)
    day_abbr = now.strftime("%a")  # e.g., 'Mon', 'Tue', ...
    if day_abbr not in sched.get("days", []):
        return False

    try:
        start_h, start_m = map(int, (sched.get("start", "00:00")).split(":"))
        end_h, end_m = map(int, (sched.get("end", "23:59")).split(":"))
        start_t = time(start_h, start_m)
        end_t = time(end_h, end_m)
    except Exception:
        return True  # fallback: ignore invalid times

    now_t = now.time()
    if start_t <= now_t <= end_t:
        return True
    return False

def get_latest_network_call(driver, target: str):
    import gzip
    import json
    import zlib

    """
    Finds and returns the most recent Selenium Wire network request
    whose URL contains the given target substring.

    Returns:
        {
            "url": str,
            "data": any,          # dict / list / None / gwt_list
            "raw_text": str,
            "kind": "json" | "gwt_rpc" | "text"
        }
    """

    seen = set()
    matches = []

    for req in driver.requests:
        if req.response and target in req.url:
            matches.append(req)

    if not matches:
        print(f"No network calls found matching '{target}'")
        return {"url": "", "data": [], "raw_text": "", "kind": "none"}

    # Pick the most recent request
    req = matches[-1]
    print(f"\nMost recent match: {req.url}")

    body_bytes = req.response.body
    try:
        body_hash = hash(body_bytes)
        if body_hash in seen:
            print("Already processed this response, skipping.")
            return {"url": "", "data": [], "raw_text": "", "kind": "none"}
        seen.add(body_hash)
    except Exception:
        pass

    # ---- Detect gzip compression ----
    is_gzip = False
    try:
        headers = req.response.headers or {}
        ce = None
        if isinstance(headers, dict):
            for k, v in headers.items():
                if k.lower() == "content-encoding":
                    ce = v
                    break
        else:
            for k, v in headers:
                if k.lower() == "content-encoding":
                    ce = v
                    break
        if ce and "gzip" in ce.lower():
            is_gzip = True
    except Exception:
        pass

    if not is_gzip and isinstance(body_bytes, (bytes, bytearray)) and body_bytes[:2] == b"\x1f\x8b":
        is_gzip = True

    # ---- Decompress if needed ----
    try:
        if is_gzip:
            try:
                decompressed = gzip.decompress(body_bytes)
            except OSError:
                decompressed = zlib.decompress(body_bytes, 16 + zlib.MAX_WBITS)
            text = decompressed.decode("utf-8", "ignore")
        else:
            text = body_bytes.decode("utf-8", "ignore")
    except Exception as e:
        print("Failed to decode/decompress body:", e)
        print("Raw preview:", body_bytes[:500])
        return {"url": "", "data": [], "raw_text": "", "kind": "error"}

    # ---- Try JSON first ----
    try:
        data = json.loads(text)
        print("Successfully parsed JSON response.")
        if isinstance(data, dict):
            print("Top-level keys:", list(data.keys())[:20])
        elif isinstance(data, list):
            print("Array length:", len(data))
        return {"url": req.url, "data": data, "raw_text": text, "kind": "json"}
    except Exception:
        pass  # fall through to GWT-RPC detection

    # ---- Try to parse Transporeon / GWT-RPC style //OK[...] ----
    def parse_gwt_rpc_inner_array(s: str):
        """
        Look for the inner array that starts with
        [\"com.transporeon.tisys2.webclient.shared.actionresult.LoadPagedTransportListItemsResult...
        and return it as a Python list if possible.
        """
        if not s.startswith("//OK["):
            return None

        marker = '["com.transporeon.tisys2.webclient.shared.actionresult.LoadPagedTransportListItemsResult'
        idx = s.find(marker)
        if idx == -1:
            return None

        # find the '[' that starts this array
        start = s.rfind('[', 0, idx + 1)
        if start == -1:
            return None

        # walk forward to find the matching closing ']'
        depth = 0
        end = None
        for i, ch in enumerate(s[start:], start):
            if ch == '[':
                depth += 1
            elif ch == ']':
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break

        if end is None:
            return None

        array_str = s[start:end]
        try:
            arr = json.loads(array_str)
            return arr
        except Exception:
            return None

    gwt_list = parse_gwt_rpc_inner_array(text)
    if gwt_list is not None:
        print("Detected GWT-RPC Transporeon payload. Parsed inner array.")
        print(f"Length of inner array: {len(gwt_list)}")
        # At this point gwt_list is a flat list of types + values.
        # You can experiment with indices to map it to a 'table'.
        return {"url": req.url, "data": gwt_list, "raw_text": text, "kind": "gwt_rpc"}

    # ---- Fallback: just return text ----
    print("Response not JSON/GWT-RPC (or could not parse). Text preview:\n", text[:500])
    return {"url": req.url, "data": None, "raw_text": text, "kind": "text"}

def refresh_page(driver, sleep_time=120):
    """Refreshes the load tender board page"""
    from Utilities.countdown import countdown
    driver.requests.clear()
    driver.refresh()
    print("refreshed page")
    countdown(sleep_time)

def navigate_to_bid_screen(driver, screen, timeout=10):
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait as W
    from selenium.webdriver.support import expected_conditions as EC
    import re
    """
    Finds the <li> whose 2nd <span> text equals `screen`, clicks it,
    and returns the total loads from the 3rd <span>.

    Returns: (success: bool, load_count: Optional[int])
    """
    panel_xpath = "//*[@id='right']/div/div[2]/nav/ul/tmx-expansion-panel"
    wait = W(driver, timeout)

    try:
        panel = wait.until(EC.presence_of_element_located((By.XPATH, panel_xpath)))
        lis = wait.until(EC.presence_of_all_elements_located(
            (By.XPATH, panel_xpath + "/li")
        ))
    except Exception:
        return False, None

    for li in lis:
        try:
            # 2nd span = screen name
            name_el = li.find_element(By.XPATH, "./a/span[2]")
            name_txt = (name_el.text or "").strip()

            if name_txt == screen:
                # 3rd span = count
                count_txt = ""
                try:
                    count_el = li.find_element(By.XPATH, "./a/span[3]")
                    count_txt = (count_el.text or "").strip()
                except Exception:
                    pass

                m = re.search(r"\d+", count_txt)
                load_count = int(m.group()) if m else 0

                # Scroll & click (JS fallback for not-interactable issues)
                driver.execute_script("arguments[0].scrollIntoView({block:'center'});", name_el)
                try:
                    name_el.click()
                except Exception:
                    driver.execute_script("arguments[0].click();", name_el)

                print(f"Navigated to {screen} (loads={load_count})")
                return True, load_count

        except Exception:
            # Ignore this li and try the next one
            continue

    # Not found
    return False, None

def get_total_loads(driver):
    """Gets the total number of loads on the page"""
    from Utilities.utils import web_driver_wait_by_xpath
    from selenium.webdriver.common.by import By
    total_number_load_results = 0
    try:
        no_transport_available_text = web_driver_wait_by_xpath(driver, 3, "//*[@id='PublishedTransportListViewCarrierGrid']/div[2]/div/table/tbody/tr/td/div").text
        print(no_transport_available_text)
        if no_transport_available_text == "No transports available":
            print("No loads found. Refreshing Page")
            return total_number_load_results
    except Exception as e:
        print(e)
        pass
    #TODO: Using this xpath I need to count how many tbody elements are directly under the table element //*[@id="PublishedTransportListViewCarrierGrid"]/div[2]/div/table
    total_number_load_results = driver.find_element(By.XPATH, "//*[@id='PublishedTransportListViewCarrierGrid']/div[2]/div/table").find_elements(By.TAG_NAME, "tbody")
    total_number_load_results = len(total_number_load_results)
    print(f"Total Number of Loads: {total_number_load_results}")
    return total_number_load_results

def get_load_information(driver, load_list_results, rown):
    """Gets load information from load_board"""
    from Utilities import storage
    from Utilities.utils import web_driver_wait_by_xpath, get_state, wait_text_by_xpath, normalize_country
    from Utilities.countdown import countdown
    from selenium.webdriver.common.keys import Keys
    import time
    import traceback

    load = {}
    row_index = rown + 1  # convenience so we don't repeat rown + 1 everywhere

    # Navigate to load details screen
    countdown(4)

    # This is a template for getting load info //*[@id="PublishedTransportListViewCarrierGrid"]/div[2]/div/table/tbody[2]/tr[1]/td[7]/div/a 
    load['bid_type'] = 'allin'

    # ID (use wait_text_by_xpath for text, web_driver_wait_by_xpath for click)
    id_xpath = f"//*[@id='PublishedTransportListViewCarrierGrid']/div[2]/div/table/tbody[{row_index}]/tr/td[5]"
    load["id"] = wait_text_by_xpath(driver, 3, id_xpath)
    web_driver_wait_by_xpath(driver, 3, id_xpath).click()
    print(load["id"])

    # Skip if we've already seen this load
    if any(load['id'] == l['id'] for l in load_list_results) or any(load['id'] == dsm for dsm in storage.dsm_list):
        print("Load already in list")
        return {}

    # Origin details
    load['origin_city'] = wait_text_by_xpath(driver, 3, f"//*[@id='PublishedTransportListViewCarrierGrid']/div[2]/div/table/tbody[{row_index}]/tr/td[25]")
    load['origin_zip'] = wait_text_by_xpath(driver, 3, f"//*[@id='PublishedTransportListViewCarrierGrid']/div[2]/div/table/tbody[{row_index}]/tr/td[24]")
    load['origin_state'] = get_state(load['origin_zip'])
    load['origin_country'] = wait_text_by_xpath(driver, 3, f"//*[@id='PublishedTransportListViewCarrierGrid']/div[2]/div/table/tbody[{row_index}]/tr/td[27]")
    load['origin_country'] = normalize_country(load['origin_country'])
    # Shipper
    load['shipper'] = wait_text_by_xpath(driver, 5, f"//*[@id='PublishedTransportListViewCarrierGrid']/div[2]/div/table/tbody[{row_index}]/tr/td[7]" )
    # Destination details
    load['dest_city'] = wait_text_by_xpath(driver, 3, f"//*[@id='PublishedTransportListViewCarrierGrid']/div[2]/div/table/tbody[{row_index}]/tr/td[33]")
    load['dest_zip'] = wait_text_by_xpath(driver, 3, f"//*[@id='PublishedTransportListViewCarrierGrid']/div[2]/div/table/tbody[{row_index}]/tr/td[32]")
    load['dest_state'] = get_state(load['dest_zip'])
    load['dest_country'] = wait_text_by_xpath(driver, 3, f"//*[@id='PublishedTransportListViewCarrierGrid']/div[2]/div/table/tbody[{row_index}]/tr/td[35]")
    load['dest_country'] = normalize_country(load['dest_country'])
    # Other load fields
    load["volume"] = wait_text_by_xpath(driver, 3, f"//*[@id='PublishedTransportListViewCarrierGrid']/div[2]/div/table/tbody[{row_index}]/tr/td[47]")
    load["quantity"] = ''
    load['ref'] = ''
    load['reason'] = ''
    load['pickup_date'] = wait_text_by_xpath(driver, 3, f"//*[@id='PublishedTransportListViewCarrierGrid']/div[2]/div/table/tbody[{row_index}]/tr/td[16]")
    load['delivery_date'] = wait_text_by_xpath(driver, 3, f"//*[@id='PublishedTransportListViewCarrierGrid']/div[2]/div/table/tbody[{row_index}]/tr/td[18]")
    load["length"] = ''
    load["is_hot"] = False
    load["weight"] = wait_text_by_xpath(driver, 3, f"//*[@id='PublishedTransportListViewCarrierGrid']/div[2]/div/table/tbody[{row_index}]/tr/td[46]")
    load['equipment'] = wait_text_by_xpath(driver, 3, f"//*[@id='PublishedTransportListViewCarrierGrid']/div[2]/div/table/tbody[{row_index}]/tr/td[45]")
    load['stops'] = []
    load['multistop'] = "N"
    load['bid_recommended'] = 0
    load['amount'] = 0
    load['accessorials'] = []

    if "8\" tarps" in load['equipment']:
        load['accessorials'].append("Tarps 8ft")

    if "Krono" in load['shipper']:
        load['shipper'] = "Kronospan"

    return load

def handle_load_error(main_driver):
    from Utilities.logger_config import logger
    from Utilities.utils import web_driver_wait_by_xpath
    from Utilities.countdown import countdown

    try:
        if "503" in web_driver_wait_by_xpath(main_driver, 5, "/html/body/h1").text:
            print("503 Service unavailable")
            logger.error("503 service error occurred", exc_info=True)
            return "503_error"
        try:
            countdown(1)
            web_driver_wait_by_xpath(main_driver, 5, "//input[@name='loginId']").send_keys("user")
            return "login_page"
        except:
            pass
    except Exception as e:
        print(e)
        logger.error(f"The following error occured where only a 503 error normaly occurs: {e}", exc_info=True)
        print("Ran into an error while grabbing the total number of loads and reloading the page")
        return "unexpected_error"


def handle_evraz_condition(load, evraz_wait_flag, evraz_wait_count):
    if load['shipper'].strip().upper() == 'EVRAZ':
        evraz_wait_flag = 0 if evraz_wait_count == 5 else 1
        evraz_wait_count = 0 if evraz_wait_flag == 0 else evraz_wait_count + 1
    return evraz_wait_flag, evraz_wait_count

def bid_load(driver, load, rown, amount):
    """Accepts load on load board"""
    from Utilities.logger_config import logger
    from Utilities.utils import web_driver_wait_by_xpath, save_page_source
    from selenium.webdriver.common.keys import Keys
    from Utilities.countdown import countdown
    from Utilities import storage
    from Utilities.email import send_error_email, send_acception_email
    import traceback
    from Utilities.utils import save_screenshot
    if storage.config["bidding"] == 0:
        return False
    try:
        web_driver_wait_by_xpath(driver, 5, "//*[@id='placeOffer']").click()
    except Exception as e:
        error_message = traceback.format_exc()
        print(error_message)
        save_page_source(driver, 'could_not_click_bid_button')
        save_screenshot(driver, 'could_not_click_bid_button')
        send_error_email(['it-dev@paulinc.com'], "Transporeon", error_message)
        print("Could not click bid button")
    time.sleep(1)
    try:
        web_driver_wait_by_xpath(driver, 5, "//*[@id='amount-preDecimals-input']").send_keys(amount)
        # Submit rate
        web_driver_wait_by_xpath(driver, 5, "//*[@id='PlaceOfferDialogPlaceButton']/div/div").click()
    except Exception as e:
        error_message = traceback.format_exc()
        print(error_message)
        save_page_source(driver, 'could_not_click_submit and send keys')
        save_screenshot(driver, 'could_not_click_submit and send keys')
        send_error_email(['it-dev@paulinc.com'], "Transporeon", error_message)
        print("Could not click on submit counteroffer")
    print('=============Bidding=============')
    send_acception_email(['it-dev@paulinc.com'], "Transporeon", load)
    storage.save_load_to_db(load)
    storage.load_data()
    return True

def multistop_check(driver, load):
    from Utilities import storage
    from Utilities.utils import web_driver_wait_by_xpath
    from Utilities.logger_config import logger
    xpath = "/html/body/table/tbody/tr/td/table[2]/tbody/tr/td/div/table/tbody/tr/td/table[8]/tbody"
    try:
        # Find the element using XPath
        tbody = web_driver_wait_by_xpath(driver, 5, xpath)
        # Find all <tr> elements within the tbody and count them
        tr_elements = tbody.find_elements_by_tag_name('tr')
        if len(tr_elements) > 3:
            load['reason'] = load['reason'] + ' Multi-stop load'
            return True
    except Exception as e:
        print(f"Element not found for the given XPath: {e}")
        logger.error(f"The following error occured when the bot was checking for multistop loads: {e}", exc_info=True)
    return False

def reject_load(driver, load):
    """Accepts load on load board"""
    from Utilities.logger_config import logger
    from Utilities import storage

    print('=============REJECTED=============')
    logger.info("Load rejected")
    load['bid_recommended'] = 0
    storage.save_load_to_db(load)

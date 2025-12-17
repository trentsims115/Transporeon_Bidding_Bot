"""This modules incudes functions that will take in a load and say whether or not we should take that load"""
from Utilities.utils import check_time, calculate_days_in_future, current_day_of_week, round_to_increment
from Utilities import storage
from Utilities.call_eia import get_surcharge_per_mile
from Utilities.logger_config import logger
from datetime import datetime, timedelta, timezone, date
import re
import traceback



def get_lead_time_code(pickup_str):
    """
    Given an ISO-like pickup datetime string such as:
        '2025-11-11T09:29:00-06:00|CST6CDT'  or  '2025-11-11T09:29:00-06:00'
    returns a code such as:
        'PICKUP_TODAY', 'PICKUP_LT_8H', 'PICKUP_LT_12H', 'PICKUP_TOMORROW', etc.
    """

    # --- 1. Normalize input ---
    if "|" in pickup_str:
        pickup_str = pickup_str.split("|")[0]

    # Parse the ISO string (Python 3.9+ handles -06:00 natively)
    try:
        pickup_dt = datetime.fromisoformat(pickup_str)
    except Exception:
        # Fallback: try stripping TZ offset manually
        pickup_dt = datetime.fromisoformat(re.sub(r"([+-]\d{2}:\d{2}).*", r"\1", pickup_str))

    # Get "now" in the same timezone offset (approx)
    now = datetime.now(pickup_dt.tzinfo or timezone.utc)

    # --- 2. Compute difference ---
    delta = pickup_dt - now
    hours_ahead = delta.total_seconds() / 3600.0
    days_ahead = delta.days
    weekday_now = now.weekday()  # 0=Mon ... 6=Sun

    # --- 3. Generate lead time codes ---
    # Same-day logic
    if pickup_dt.date() == now.date():
        if hours_ahead < 0:
            return "PICKUP_YDAY_OR_PRIOR"
        elif hours_ahead < 8:
            return "PICKUP_LT_8H"
        elif hours_ahead < 12:
            return "PICKUP_LT_12H"
        else:
            # late same-day (beyond noon)
            if pickup_dt.hour >= 14:
                return "PICKUP_SAME_DAY_AFTER_2PM"
            elif pickup_dt.hour >= 12:
                return "PICKUP_SAME_DAY_AFTER_12PM"
            elif pickup_dt.hour >= 10:
                return "PICKUP_SAME_DAY_AFTER_10AM"
            else:
                return "PICKUP_TODAY"

    # Tomorrow logic
    if pickup_dt.date() == (now + timedelta(days=1)).date():
        if pickup_dt.hour < 10:
            return "PICKUP_NEXT_DAY_BEFORE_10AM"
        elif 10 <= pickup_dt.hour < 12:
            return "PICKUP_NEXT_DAY_10_12"
        elif pickup_dt.hour >= 12:
            return "PICKUP_NEXT_DAY_AFTER_12PM"
        else:
            return "PICKUP_TOMORROW"

    # Past date
    if pickup_dt < now:
        return "PICKUP_YDAY_OR_PRIOR"

    # Weekend logic
    if pickup_dt.weekday() >= 5:
        # 5=Saturday,6=Sunday
        return "PICKUP_WEEKEND"

    # More granular next-day logic for business rules
    next_day = (pickup_dt - now).days == 1
    if next_day and weekday_now <= 3:  # Mon–Thu
        return "PICKUP_NEXT_DAY_MON_THU"
    if next_day and weekday_now >= 4:  # Fri–Sun
        return "PICKUP_NEXT_DAY_FRI_SUN"

    # More than 2 days away
    if 1 < days_ahead <= 3:
        return "PICKUP_WITHIN_3DAYS"
    if days_ahead > 3:
        return "PICKUP_FUTURE"

    return "PICKUP_UNKNOWN"

def normalize_dt(dt_str):
    """
    Normalize a date or datetime string into a datetime object.
    Handles formats like:
      - '2025-12-16'
      - '2025-12-03T13:37:00-06:00|CST6CDT'
    Returns None if parsing fails.
    """
    try:
        if not dt_str:
            return None

        # Ensure it's a string
        dt_str = str(dt_str).strip()

        # If string contains a timezone indicator (| or similar),
        # strip off everything after '|'
        if "|" in dt_str:
            dt_str = dt_str.split("|")[0].strip()

        # Try full ISO format first (example: 2025-12-03T13:37:00-06:00)
        try:
            return datetime.fromisoformat(dt_str)
        except Exception:
            pass

        # Try simple date format (example: 2025-12-16)
        try:
            d = datetime.strptime(dt_str, "%Y-%m-%d").date()
            return datetime(d.year, d.month, d.day)
        except Exception:
            pass

        # Add more patterns here if needed

        # If nothing worked, return None
        return None

    except Exception:
        print("Error normalizing datetime:")
        traceback.print_exc()
        return None

def is_not_sunday(date_str):
    # Convert the string to a datetime object
    date_obj = datetime.strptime(date_str, '%Y-%m-%d')
    
    # Check if the day of the week is a Sunday (6)
    if date_obj.weekday() == 6:
        return False
    else:
        return True


def get_current_pickup_day_count(oc, os, shipper, pickup_date, pickup_day_load_limit):
    """
    Returns the correct count for the given lane and shipper. If a match cannot be made, return 0
        oc: origin city to use
        os: origin state to use
        shipper: shipper to use
        pickup_date: the date of the current load pick_up_date (any format handled by normalize_dt)
        pickup_day_load_limit: list of counts by pickup_date, origin, and shipper
            [
                {'Origin': 'BOONEVILLE-MS', 'Shipper': 'Westlake Chemical', 'PickUp_Date': '2023-08-07', 'Cnt': 4},
                {'Origin': 'Yucca-AZ', 'Shipper': 'Westlake Chemical', 'PickUp_Date': '2023-08-04', 'Cnt': 3},
                ...
            ]
    """
    # Normalize origin & shipper for consistent comparison
    origin = f"{oc}-{os}".upper()
    shipper_norm = shipper.upper()

    # Normalize the incoming pickup_date to just the date
    pickup_dt = normalize_dt(pickup_date)
    if pickup_dt is None:
        return 0
    target_day = pickup_dt.date()

    for record in pickup_day_load_limit:
        # Handle both 'Origin' and 'origin' keys, etc.
        rec_origin = (record.get('Origin') or record.get('origin') or "").upper()
        rec_shipper = (record.get('Shipper') or record.get('shipper') or "").upper()

        # Get the record's pickup date string from possible keys
        rec_pickup_str = (
            record.get('PickUp_Date') or
            record.get('Pickup_Date') or
            record.get('pickup_date') or
            record.get('pick_up_date')
        )

        rec_dt = normalize_dt(rec_pickup_str)
        if rec_dt is None:
            continue
        rec_day = rec_dt.date()

        if rec_origin == origin and rec_shipper == shipper_norm and rec_day == target_day:
            # Handle 'Cnt' or 'cnt' key
            return record.get('Cnt') or record.get('cnt') or 0

    # Return 0 if no match found
    return 0

def get_current_pickup_day_count_shipper(shipper, pickup_date, pickup_day_load_limit):
    """
    Returns the correct count for the given lane and shipper. If a match cannot be made, return 0
        shipper: shipper to use
        pickup_date: the date of the current load pick_up_date
        pickup_day_load_limit: list of counts by pickup_date, origin, and shipper
            [
                {'Origin': 'BOONEVILLE-MS', 'Shipper': 'Westlake Chemical', 'PickUp_Date': '2023-08-07', 'Cnt': 4},
                {'Origin': 'Yucca-AZ', 'Shipper': 'Westlake Chemical', 'PickUp_Date': '2023-08-04', 'Cnt': 3},
                ...
            ]
    """
    # Convert shipper to lowercase
    shipper = shipper.upper()

    # Search for the matching record in pickup_day_load_limit
    for record in pickup_day_load_limit:
        if (record['shipper'].upper() == shipper and
            record['pickup_date'] == pickup_date):
            return record['cnt']
    # Return 0 if no match found
    return 0

def _parse_json_array(val):
    """Accepts None, JSON string, or list; returns list[str]."""
    import json
    if val is None or val == "":
        return []
    if isinstance(val, list):
        return val
    try:
        out = json.loads(val)
        return out if isinstance(out, list) else []
    except Exception:
        return []

def _is_weekend(dt):
    # 5=Sat, 6=Sun
    return dt.weekday() >= 5

def _day_matches(rule_val, dt):
    """rule_val: 'WEEKDAY'|'WEEKEND'|'ANY'|None  -> True if matches."""
    if not rule_val or rule_val == 'ANY':
        return True
    if rule_val == 'WEEKEND':
        return _is_weekend(dt)
    if rule_val == 'WEEKDAY':
        return not _is_weekend(dt)
    return True

def _multi_match(rule_values, load_values, mode_any_all, exact_match=False):
    """
    rule_values: list[str]      (from rule JSON)
    load_values: iterable[str]  (from load)
    mode_any_all: 'ANY'|'ALL'
    exact_match: if True, both lists must match exactly (as sets)

    Empty rule_values -> no constraint (match True).
    """
    if not rule_values:
        return True

    s_rule = set(v.strip().lower() for v in rule_values if v)
    s_load = set(v.strip().lower() for v in (load_values or []) if v)

    if not s_rule:
        return True

    # --- Exact-match mode (used for accessorials) ---
    if exact_match:
        return s_rule == s_load

    # --- Normal ANY / ALL logic ---
    if mode_any_all == 'ALL':
        return s_rule.issubset(s_load)

    # ANY mode
    return len(s_rule.intersection(s_load)) > 0

def _equipment_matches(rule_equipment_multi, legacy_single, load_equipment):
    """
    If multi list present -> use it. Else fall back to legacy single.
    Empty -> no constraint.
    """
    rule_multi = [e for e in _parse_json_array(rule_equipment_multi) if e and e != '*']
    if rule_multi:
        return _multi_match(rule_multi, [load_equipment], 'ANY')  # ANY of listed equipment types
    # legacy
    if not legacy_single or legacy_single == '*' or legacy_single.strip() == '':
        return True
    return (str(load_equipment or '').strip().lower() == legacy_single.strip().lower())

def _lead_time_matches(rule_code, load_code):
    # If rule has no code -> no constraint. Else require equality.
    if not rule_code:
        return True
    return (str(load_code or '') == str(rule_code))

def _weight_matches(min_lbs, max_lbs, load_weight):
    if load_weight is None:
        # if rule constrains weight but load has none, treat as non-match
        return (min_lbs is None and max_lbs is None)
    if min_lbs is not None and load_weight < int(min_lbs):
        return False
    if max_lbs is not None and load_weight > int(max_lbs):
        return False
    return True

def _stops_extra_amount(threshold, per_extra_usd, stops_count):
    """
    If threshold is set and stops_count >= threshold, add per_extra_usd for each stop over (threshold-1),
    i.e. threshold=3 means 3rd and up are "extra". If max_allowed is set and exceeded, still add extras
    but caller may decide to reject elsewhere if desired.
    """
    if not threshold or not per_extra_usd:
        return 0.0
    try:
        t = int(threshold)
        s = int(stops_count or 0)
        if s >= t:
            extras = max(0, s - (t - 1))
            return float(per_extra_usd) * extras
        return 0.0
    except Exception:
        return 0.0

def _variable_adjustment_from_rule(restriction, base_rate):
    """
    Uses new variable fields: op, calc_type, dollar_value, pct_value, target_variable.
    Returns (adj_value, reason, is_set)
    """
    adj = 0.0
    reason = ""
    is_set = False

    if not restriction.get('variable_id'):
        return 0.0, reason, False

    op         = (restriction.get('op') or 'ADD').upper()
    calc_type  = (restriction.get('calc_type') or 'DOLLAR').upper()
    dollar_val = float(restriction.get('dollar_value') or 0.0)
    pct_val    = float(restriction.get('pct_value') or 0.0)
    target_var = (restriction.get('target_variable') or 'base_rate').lower()

    basis = float(base_rate)
    pct_amount    = (pct_val / 100.0) * basis
    dollar_amount = dollar_val

    if calc_type == 'HYBRID_MAX':
        raw = max(dollar_amount, pct_amount)
        calc_desc = f"max(${dollar_amount:.2f}, {pct_val:.3f}% of {target_var}=${pct_amount:.2f})"
    elif calc_type == 'HYBRID_MIN':
        raw = min(dollar_amount, pct_amount)
        calc_desc = f"min(${dollar_amount:.2f}, {pct_val:.3f}% of {target_var}=${pct_amount:.2f})"
    elif calc_type == 'PCT_OF_VAR':
        raw = pct_amount
        calc_desc = f"{pct_val:.3f}% of {target_var}=${pct_amount:.2f}"
    else:
        raw = dollar_amount
        calc_desc = f"${dollar_amount:.2f}"

    if op == 'SUBTRACT':
        adj = -raw
        op_txt = "subtract"
    elif op == 'SET':
        adj = raw
        op_txt = "SET"
        is_set = True
    else:  # ADD
        adj = raw
        op_txt = "add"

    reason = f"{op_txt} {calc_desc}"
    return adj, reason, is_set

def check_lane_restrictons(load, base_rate):
    """
    Runs through EVERY rule:
      * Adds the variable amounts for each matching rule (and per-extra-stop premium)
      * Only stops early if rule is 'no_bid'
      * Accumulates human-readable reasons in load['reason']
    """
    origin_city = load['origin_city'].strip().upper()
    origin_state = load['origin_state'].strip().upper()
    origin_country = load['origin_country'].strip().upper()
    destination_city = load['dest_city'].strip().upper()
    destination_state = load['dest_state'].strip().upper()
    destination_country = load['dest_country'].strip().upper()
    shipper_name = load['shipper'].strip().upper()

    # Optional load attributes for new conditions (safely defaulted)
    pickup_dt   = load.get('pickup_date')   # datetime/date
    delivery_dt = load.get('delivery_date') # datetime/date
    lead_time_code = load.get('lead_time_code')
    accessorials = load.get('accessorials') or []
    load_equipment = load.get('equipment_type') or load.get('equipment') or ''
    weight_lbs = load.get('weight').replace("lb", "").replace(" ", "").replace(",", "").replace("s", "").replace("S", "")
    stops_count = len(load.get('stops')) or 2
    load['bid_mode'] = storage.config["bidding"]

    # normalize types
    pickup_dt = normalize_dt(pickup_dt)
    delivery_dt = normalize_dt(delivery_dt)

    amount = float(base_rate)
    load['bid_recommended'] = True
    reasons = []
    locked_by_set = False

    for restriction in storage.lane_restrictions:
        # Normalize restriction fields for lane/shipper match
        restriction['origin_city']  = restriction['origin_city'].strip().upper()  if restriction['origin_city']  else None
        restriction['origin_state'] = restriction['origin_state'].strip().upper() if restriction['origin_state'] else None
        restriction['dest_city']    = restriction['dest_city'].strip().upper()    if restriction['dest_city']    else None
        restriction['dest_state']   = restriction['dest_state'].strip().upper()   if restriction['dest_state']   else None
        restriction['shipper_name'] = restriction['shipper_name'].strip().upper() if restriction['shipper_name'] else None

        # ---- Lane+shipper match (required) ----
        if not (
            restriction['shipper_name'] == shipper_name and
            (restriction['origin_state'] == origin_state or restriction['origin_state'] == '*') and
            (origin_city == restriction['origin_city'] or restriction['origin_city'] == '*') and
            (origin_country == restriction['origin_country'] or restriction['origin_country'] == '*') and
            (restriction['dest_state'] == destination_state or restriction['dest_state'] == '*') and
            (restriction['dest_city'] == destination_city or restriction['dest_city'] == '*') and
            (restriction['dest_country'] == destination_country or restriction['dest_country'] == '*') and
            (load['bid_type'] == restriction['linehaul_or_allin'] or restriction['linehaul_or_allin'] == 'both')
        ):
            continue

        # ---- Extra condition checks (all must pass) ----
        pickup_ok = True
        if restriction.get('pickup_day') and pickup_dt:
            pickup_ok = _day_matches(restriction.get('pickup_day'), pickup_dt)

        # ---- Extra condition checks (all must pass) ----
        distance_range_ok = True
        if restriction.get('distance_low') and restriction.get('distance_high'):
            if load['est_distance'] >= restriction.get('distance_low') and load['est_distance'] <= restriction.get('distance_high'):
                distance_range_ok = True
            else:
                distance_range_ok = False

        lane_count_ok = True
        pickup_day_load_cnt = get_current_pickup_day_count(origin_city, origin_state, shipper_name, load['pickup_date'], storage.pickup_day_load_cnt)
        if restriction.get('pickup_day_lane_count_min') and restriction.get('pickup_day_lane_count_max'):
            if pickup_day_load_cnt >= restriction.get('pickup_day_lane_count_min') and pickup_day_load_cnt <= restriction.get('pickup_day_lane_count_max'):
                lane_count_ok = True
            else:
                lane_count_ok = False

        delivery_ok = True
        if restriction.get('delivery_day') and delivery_dt:
            delivery_ok = _day_matches(restriction.get('delivery_day'), delivery_dt)

        # Specific dates (exact match) if provided on rule
        spec_pick_ok = True
        if restriction.get('specific_pickup_date'):
            try:
                spec_pick_ok = bool(pickup_dt and str(pickup_dt.date()) == str(restriction['specific_pickup_date']))
            except Exception:
                spec_pick_ok = False
        spec_del_ok = True
        if restriction.get('specific_delivery_date'):
            try:
                spec_del_ok = bool(delivery_dt and str(delivery_dt.date()) == str(restriction['specific_delivery_date']))
            except Exception:
                spec_del_ok = False

        lead_ok = _lead_time_matches(restriction.get('lead_time_code'), lead_time_code)

        acc_ok = _multi_match(
            _parse_json_array(restriction.get('accessorials')),
            accessorials,
            mode_any_all=(restriction.get('accessorials_match') or 'ANY'),
            exact_match=True  # <-- enforce exact matching
        )

        equip_ok = _equipment_matches(
            restriction.get('equipment_types'),
            restriction.get('equipment_type'),
            load_equipment
        )

        weight_ok = _weight_matches(
            restriction.get('min_weight_lbs'),
            restriction.get('max_weight_lbs'),
            int(weight_lbs) if weight_lbs is not None else None
        )

        if not (pickup_ok and delivery_ok and spec_pick_ok and spec_del_ok and lead_ok and acc_ok and equip_ok and weight_ok and distance_range_ok and lane_count_ok):
            continue  # this rule doesn't apply beyond lane

        # If rule is "no bid", stop immediately
        if restriction.get('no_bid'):
            load['bid_failure_reason'] = f"Rule {restriction['rule_id']}: NO BID (matched lane & conditions)"
            load['bid_recommended'] = False
            return False, 0

        # Variable adjustment
        if restriction.get('variable_id'):
            var_adj, var_reason, is_set = _variable_adjustment_from_rule(restriction, base_rate)
            if is_set:
                amount = var_adj
                reasons.append(f"Rule {restriction['rule_id']}: SET final bid → {var_reason}")
                locked_by_set = True
                break
            elif var_adj:
                amount += var_adj
                reasons.append(f"Rule {restriction['rule_id']}: {var_reason}")

        # Per-extra-stop premium (if configured)
        extra = _stops_extra_amount(
            restriction.get('min_stops_threshold'),
            restriction.get('per_extra_stop_usd'),
            stops_count
        )
        print()
        if restriction.get('max_stops_allowed') and stops_count > restriction.get('max_stops_allowed'):
            return False, 0
        if extra:
            amount += extra
            reasons.append(
                f"Rule {restriction['rule_id']}: multistop premium +${float(restriction.get('per_extra_stop_usd')):.2f}/extra "
                f"(stops={stops_count}, threshold={restriction.get('min_stops_threshold')})"
            )

    # If locked by SET, skip fuel adjustments and shipper rounding/min/max.
    if locked_by_set:
        load['reason'] = " | ".join(reasons) if reasons else "Locked by SET rule"
        return True, amount
    # After all rules: fuel surcharge adjustment if linehaul
    if load.get('bid_type') == 'linehaul':
        # negative because surcharge is paid separately; keep your existing logic
        amount = amount - (get_surcharge_per_mile() * load['est_distance'])
        reasons.append(f"Linehaul fuel adj: -${(get_surcharge_per_mile() * load['est_distance']):.2f}")

    # Shipper-level caps/rounding
    for s in storage.shipper_restrictions:
        if s['shipper_name'].upper() == shipper_name:
            if s.get('rounding'):
                amount = round_to_increment(amount, s.get('rounding_increment'), s.get('rounding_direction'))
                reasons.append(f"Shipper rounding → incr={s.get('rounding_increment')} dir={s.get('rounding_direction')}")
            if s.get('max_bid') and (s['max_bid'] < amount):
                amount = s['max_bid']; reasons.append(f"Shipper max cap → ${amount:.2f}")
            if s.get('min_bid') and (s['min_bid'] > amount):
                amount = s['min_bid']; reasons.append(f"Shipper min floor → ${amount:.2f}")
            if (s.get('bid_mode') or '').lower() == "no_bid":
                reasons.append("Shipper bid mode: NO BID")
                load['bid_mode'] = 0
                load['bid_recommended'] = False
                load['reason'] = " | ".join(reasons)
                return False, amount

    load['reason'] = " | ".join(reasons) if reasons else "No rule matched; base rate"
    return True, amount

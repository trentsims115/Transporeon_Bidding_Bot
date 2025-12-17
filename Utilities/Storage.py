"""This is the defintion of the Storage class, which is responsible for: Saving data, recieving data, and managing the database connection"""
import mysql.connector
import time
from prometheus_client import Gauge
from Utilities.logger_config import logger
from Utilities.utils import get_date_with_offset, check_day, check_time, time_now
import json


class Storage:
    def __init__(self, config):
        # self._is_connected = False
        self.SQL_connection_state = Gauge(
                 "SQL_connection_state",
                 "This shows whether or not the bot is connected to SQL currently",
             )
        self.should_grab_loads = Gauge(
            "should_grab_loads",
            "This tells the bot whether or not it should be grabbing loads"
        )
        self.should_grab_loads.set(1)
        self.max_retry = 5
        self.load_board = "Transporeon"
        self.user_data = []
        self.lane_restrictions = []
        self.shipper_restrictions = []
        self.pickup_day_load_cnt = []
        self.dsm_list = []
        self._connection = None
        self.connect()
        self._connection.autocommit = True
        self.get_user_data()
        self.load_data()
        self.config = config

    def connect(self):
        """This function can be used to reconnect to the database if connection is loss"""
        config = {
            'user': 'bidding_user',
            'password': 'Gravel$12Quasi',
            'host': 'AVRLDS01',
            'database': 'bidding',
            'port': 3306
        }
        retry_count = 0
        while retry_count < self.max_retry:
            try:
                connection = mysql.connector.connect(**config)
                # self.is_connected = True
                print("Connected to database successfully!")
                self.SQL_connection_state.set(1)
                self._connection = connection
                return
            except mysql.connector.Error as err:
                print(f"Error: {err}")
                if retry_count > 1:  # Avoids sleep on the last iteration if still not connected
                    print("Retrying in 5 seconds...")
                    time.sleep(5)
                retry_count += 1
        self.SQL_connection_state.set(0)
        logger.error("The bot cannot connect to the database after 5 failed attempts!")
        print("Failed to connect after 5 attempts. Exiting.")
        raise ConnectionError("Unable to establish a connection to the database.")

    def is_connected(self):
        """Checks the database connection"""
        try:
            self._connection.ping()
        except:
            return False
        return True

    def close(self):
        """Closes the database connection"""
        if self.is_connected:
            self._connection.close()

    def load_data(self):
        """Loads in data from the database for lane and shipper restriction as well as a dsm list"""
        # Lane Restrictions:
        try:
            self.get_lane_restrictions()
            self.get_shipper_restrictions()
            self.get_dsm_list()
        except Exception as e:
            if not "MySQL Connection not available" in str(e):
                print("Something is wrong with a query you are using")
                logger.error("Something is wrong with a query you are using", e)
            else:
                raise ConnectionError("MySQL Connection is not available")

    def get_user_data(self):
        """
        gets the user login information for the load_board from MSSQL
            db: DB to use
            load_board: load_board to look under.
            Return: Returns a list of user data for the particular load board
        """
        sql = (
            "SELECT l.loadboard_url, a.loadboard_id, a.username, a.password "
            "FROM pli_loadboard_accounts a "
            "LEFT OUTER JOIN pli_loadboards l ON a.loadboard_id = l.id "
            f"WHERE l.loadboard_name = '{self.load_board}';"
        )
        if self.is_connected():
            my_cursor = self._connection.cursor()
            my_cursor.execute(sql)
        else:
            self.connect()
            my_cursor = self._connection.cursor()
            my_cursor.execute(sql)
        self.user_data = my_cursor.fetchall()[0]
            
    def get_lane_restrictions(self):
        """
        Gets all current lane restrictions for the current load board.
        Returns: list[dict]
        """
        data_list = []
        sql = (
            "SELECT "
            "  s.shipper_name, "
            "  r.id AS rule_id, r.shipper_id, "
            "  r.origin_city, r.origin_state, r.origin_country, r.dest_city, r.dest_state, r.dest_country, "
            "  r.variable_id, "
            "  v.variable_name, v.op, v.calc_type, v.dollar_value, v.pct_value, v.target_variable, "
            "  r.no_bid, "
            "  r.equipment_type, r.linehaul_or_allin, "

            # ---- NEW rule-targeting fields ----
            "  r.pickup_day, r.delivery_day, "
            "  r.specific_pickup_date, r.specific_delivery_date, "
            "  r.accessorials, r.accessorials_match, "
            "  r.lead_time_code, "
            "  r.min_stops_threshold, r.max_stops_allowed, r.per_extra_stop_usd, "
            "  r.min_weight_lbs, r.max_weight_lbs, "
            "  r.equipment_types, r.distance_low, r.distance_high, "
            "  r.pickup_day_lane_count_min, r.pickup_day_lane_count_max  "
            "FROM pli_bidding_rules r "
            "LEFT OUTER JOIN pli_shippers s ON s.id = r.shipper_id "
            "LEFT OUTER JOIN pli_loadboard_accounts l ON s.loadboard_id = l.loadboard_id "
            "LEFT OUTER JOIN pli_loadboards lb ON l.loadboard_id = lb.id "
            "LEFT OUTER JOIN pli_bidding_variables v ON v.id = r.variable_id "
            f"WHERE (lb.loadboard_name = '{self.load_board}' AND r.is_active = 1) "
            # allow either no variable, or an active variable
            "AND (r.variable_id IS NULL OR v.is_active = 1) "
            "ORDER BY s.id, r.origin_city, r.origin_state, r.dest_city, r.dest_state;"
        )
        if self.is_connected():
            my_cursor = self._connection.cursor()
            my_cursor.execute(sql)
        else:
            self.connect()
            my_cursor = self._connection.cursor()
            my_cursor.execute(sql)

        columns = [column[0] for column in my_cursor.description]
        for row in my_cursor.fetchall():
            data_list.append(dict(zip(columns, row)))
        self.lane_restrictions = data_list

    def get_shipper_restrictions(self):
        """
        Gets all current lane restrictions
            db: DB to use
            load_board: load board to get restrictions for
            Return: returns a list of each restriction in dictionary format
        """
        data_list = []
        sql = (
            "SELECT s.shipper_name, s.max_bid, s.min_bid, s.rounding, s.rounding_increment, s.rounding_direction, s.bid_mode "
            "FROM pli_shippers s "
            "LEFT OUTER JOIN pli_loadboards lb ON s.loadboard_id = lb.id "
            f"WHERE lb.loadboard_name = '{self.load_board}' "
        )
        if self.is_connected():
            my_cursor = self._connection.cursor()
            my_cursor.execute(sql)
        else:
            self.connect()
            my_cursor = self._connection.cursor()
            my_cursor.execute(sql)
        columns = [column[0] for column in my_cursor.description]
        for row in my_cursor.fetchall():
            data_dict = dict(zip(columns, row))
            data_list.append(data_dict)
        self.shipper_restrictions = data_list


    def get_dsm_list(self):
        """
        Gets the current DSM list for the given loadboard
            db: Database to look in
            load_board: load_board to use
        """
        dsm_list = []
        sql = f"SELECT shipment_id, creation_timestamp FROM pli_bidding WHERE creation_timestamp > '{get_date_with_offset(-7)}' and loadboard_name = '{self.load_board}';"
        if self.is_connected():
            my_cursor = self._connection.cursor()
            my_cursor.execute(sql)
        else:
            self.connect()
            my_cursor = self._connection.cursor()
            my_cursor.execute(sql)
        for row in my_cursor.fetchall():
            dsm_list.append(row[0])
        self.dsm_list = dsm_list

    def save_load_to_db(self, load):
        """
        This will save a new load to the database given load information and db
            load: load to save to db
            disposition: Result of check restrictions
        """
        sql = f"""INSERT INTO pli_bidding (
            shipment_id,
            loadboard_id,
            loadboard_name,
            account_name,
            pickup_date,
            delivery_date,
            origin_city_name,
            origin_state_code,
            origin_postal_code,
            origin_country_code,
            destination_city_name,
            destination_state_code,
            destination_postal_code,
            destination_country_code,
            distance,
            weight,
            equipment_type_code,
            dat_equipment_type_code,
            multi_stop_flag,
            hazmat_flag,
            tanker_endorsement_flag,
            team_driver_flag,
            bid_recommended,
            bid_failure_reason,
            bid_recommended_amount,
            base_rate,
            submitted_amount,
            quote_id,
            pricing_augmentation,
            pricing_augmentation_reason,
            bid_mode,
            bid_type,
            dat_response
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
        )"""
        params = (
            load['id'],
            1,
            "Transporeon",
            load['shipper'],
            load['pickup_date'],
            load['delivery_date'],
            load['origin_city'],
            load['origin_state'],
            load['origin_zip'],
            load['origin_country'],
            load['dest_city'],
            load['dest_state'],
            load['dest_zip'],
            load['dest_country'],
            load['est_distance'],
            load['weight'],
            load['equipment'],
            load['dat_equipment'],
            load['multistop'],
            "N",
            "N",
            "N",
            load['bid_recommended'],
            load['bid_failure_reason'],
            load['amount'],
            load['base_rate'],
            load['amount'],
            load['quote_id'],
            load['amount'] - load['base_rate'],
            load['reason'],
            load['bid_mode'],
            load['bid_type'],
            json.dumps(load['dat_response'])
        )
        try:
            print("Executing INSERT QUERY")
            print(sql)
            if self.is_connected():
                my_cursor = self._connection.cursor()
                my_cursor.execute(sql, params)
            else:
                self.connect()
                my_cursor = self._connection.cursor()
                my_cursor.execute(sql, params)
            self._connection.commit()
        except Exception as e:
            print(e)
            if "MySQL Connection not available" in str(e):
                print("The bot cannot connect to MYSQL!!!!")
            if "Duplicate entry" in str(e):
                print("Duplicate load in database")
            else:
                logger.error(f"The following error occured when trying to save load to MSSQL: {e}", exc_info=True)
                print('Send to SQL Failure: ', e.args)

def get_load_count(self):
        """
        Get the current load count of accepted loads by pickup date and origin city-state.
            db: database to use
            load_board: load board to use
        """
        my_cursor = self._connection.cursor()
        pickup_day_load_cnt = []
        sql = f"""
        SELECT CONCAT(pb.origin_city_name, '-', pb.origin_state_code) AS origin, 
        pb.account_name, 
        pb.pickup_date, 
        Count(*) AS cnt 
        FROM pli_bidding AS pb JOIN pli_loadboards as pl ON pl.id = pb.loadboard_id
        WHERE pickup_date >= CURDATE() and pl.loadboard_name = '{self.load_board}'
        GROUP BY CONCAT(origin_city_name, '-', origin_state_code), account_name, pickup_date 
        ORDER BY cnt DESC;
        """
        if self.is_connected():
            my_cursor = self._connection.cursor()
            my_cursor.execute(sql)
        else:
            self.connect()
            my_cursor = self._connection.cursor()
            my_cursor.execute(sql)
        columns = [column[0] for column in my_cursor.description]
        for row in my_cursor.fetchall():
            data_dict = dict(zip(columns, row))
            pickup_day_load_cnt.append(data_dict)
        self.pickup_day_load_cnt = pickup_day_load_cnt

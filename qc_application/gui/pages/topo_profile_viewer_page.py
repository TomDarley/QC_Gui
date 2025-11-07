

"""This is the Profile QC tool, GUI. Used to check all profiles going into the dash database and 
   exports saves fixed and flagged data for review."""
import sys
import os
import time
import re
import tempfile
import logging
from datetime import datetime
import shutil
import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlalchemy import text

# PyQt Imports
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QHBoxLayout, QPushButton, QLabel, QFrame, QMessageBox, QSizePolicy, QDialog, QInputDialog
)
from PyQt5.QtCore import Qt, QCoreApplication, QTimer, pyqtSignal

# Matplotlib-PyQt Integration
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar


from qc_application.config.app_settings import AppSettings


from qc_application.services.topo_calculate_cpa_service import CalculateCPATool
from qc_application.utils.calculate_easting_northings import calculate_missing_northing_easting
from qc_application.utils.profile_viewer_pure_functions import qc_profile, find_over_spacing
from qc_application.utils.database_connection import establish_connection
# --- Global Configuration and Stub Functions ---

settings = AppSettings()
USER = settings.get("user")
#-Todo- if mp has changed then need to recalculate all cpa values for that profile for all existing data in the database
#-Todo- Fixes that can be done in the profile viewer need to update the database qc tables
#-Todo - Hook into existing GUI so the tool is called from the main topo qc tool
#-Todo -Add export functions to save files on x drive

#-Todo- Fix Loaded Profile Text at the bottom of the screen, works in topo mode not MP mode



# Define script directory and log file path
script_dir = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(script_dir, 'profile_qc.log')

def configure_logging():
    """Sets up file logging for debugging."""
    if not logging.getLogger().handlers:
        logging.basicConfig(
            level=logging.DEBUG,  # Set to DEBUG for maximum detail
            format='%(asctime)s - %(levelname)s - %(name)s - %(message)s',
            handlers=[
                logging.FileHandler(LOG_FILE, mode='a', encoding='utf-8'),
                logging.StreamHandler(sys.stdout)  # Keep console output
            ]
        )
    # Silence verbose loggers
    logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)
    logging.info(f"Logging configured. Outputting to {LOG_FILE}")

# Call configuration early
configure_logging()

# Stub for the external CPA calculation class
def CalculateCPA(*args, **kwargs):
    """Stub for the external CPA calculation class."""
    logging.warning("CPA Calculation Stubbed. Returning dummy DataFrame.")

    d = CalculateCPATool(*args, **kwargs)
    new_cpa = d.calculate_cpa()

    return new_cpa


# --- Global Utility Functions ---
pd.options.display.float_format = '{:.4f}'.format

def get_data(query, conn):
    """Fetch data from the database and return as a pandas DataFrame."""
    logging.debug(f"Executing SQL query: {query[:50]}...")
    return pd.read_sql_query(query, conn)


def extract_profiles(df):
    """Extract unique profiles."""
    df = df.copy()
    df['reg_id'] = df['reg_id'].astype(str).str.strip()
    unique_profiles = df[['reg_id']].drop_duplicates().reset_index(drop=True)
    unique_profiles['reg_id'] = unique_profiles['reg_id'].astype(str).str.strip()
    logging.info(f"Extracted {len(unique_profiles)} unique profiles.")
    return unique_profiles


def extract_date(path):
    """Extract date from the file path."""
    base_name = os.path.basename(path)
    match = re.search(r'(?<!\d)(\d{8})(?!\d)', base_name)
    if match:
        date_str = match.group(1)
        date_obj = datetime.strptime(date_str, "%Y%m%d")
        logging.info(f"Extracted date {date_obj.date()} from file path.")
        return date_obj
    logging.warning(f"No date found in file path: {path}")
    return None


# --- Matplotlib Widget Integration ---
class MplCanvas(FigureCanvas):
    """A custom Matplotlib canvas for PyQt."""

    def __init__(self, parent=None, width=5, height=4, dpi=100):
        super().__init__(Figure(figsize=(width, height), dpi=dpi))
        self.axes = self.figure.add_subplot(111)
        self.setParent(parent)
        logging.debug("MplCanvas initialized.")


# --- Data and Logic Handler (Refactored ProfilePlotter) ---
class DataHandler:
    """Handles all data manipulation, file I/O, and database interactions."""
    LAST_SESSION_LOG = os.path.join(script_dir, 'Last_Session_Log', 'log.pkl')

    def __init__(self, new_survey_topo_data, survey_unit):
        logging.info(f"Initializing DataHandler for unit: {survey_unit}")

        logging.info(f"Checking if Survey Unit '{survey_unit}' has already been pushed to the database.")

        # Data Loading
        try:
            if isinstance(new_survey_topo_data, str):
                self.new_survey_topo_data = pd.read_csv(
                    new_survey_topo_data, sep='\t', dtype=str, keep_default_na=False
                )
            else:
                self.new_survey_topo_data = new_survey_topo_data.copy()
            logging.info(f"Input data loaded successfully. Total rows: {len(self.new_survey_topo_data)}")
        except Exception as e:
            logging.error(f"Failed to load initial survey data: {e}", exc_info=True)
            self.new_survey_topo_data = pd.DataFrame()

        self.new_survey_topo_data.columns = self.new_survey_topo_data.columns.str.lower()
        self.new_survey_topo_data['reg_id'] = self.new_survey_topo_data['reg_id'].astype(str).str.strip()

        # State Variables
        self.unique_profiles = extract_profiles(self.new_survey_topo_data)
        self.survey_unit = survey_unit
        self.date = extract_date(new_survey_topo_data)
        self.current_index = 0
        self.profile = None
        self.profile_data = None
        self.current_master_profiles = None

        self.edits_made = False  # Track if edits have been made

        self.added_points_x = []
        self.added_points_y = []
        self.added_profile_lines = []
        self.modified_profiles = {}

        self.historical_profiles = {}  # Dictionary to store {date_object: DataFrame}
        self.show_historical_profiles = False  # State toggle

        # Store all profile issues for the session
        self.profile_issues = {} #  Store profile QC issues

        self.flagged_reasons = {} # Store reasons and profile profiles
        self.flagged_profiles = False # Flag to indicate if any profiles were flagged during the session






        # Ensure directories exist
        for folder in [ 'Flagged_Profiles',
                       'Last_Session_Log']:
            path = os.path.join(script_dir, folder)
            os.makedirs(path, exist_ok=True)
            logging.debug(f"Ensured directory exists: {path}")

    def load_current_profile(self, force_db_load=False):
        """Loads and prepares data for the current profile index."""
        if not (0 <= self.current_index < len(self.unique_profiles)):
            logging.error(f"Index out of bounds: {self.current_index}")
            return

        current_profile_value = str(self.unique_profiles.iloc[self.current_index]['reg_id']).strip()
        self.profile = current_profile_value
        logging.info(f"Loading data for Profile: {self.profile} (Index: {self.current_index})")

        # 1. Load Initial Profile Data
        self.profile_data = self.new_survey_topo_data[
            self.new_survey_topo_data['reg_id'] == current_profile_value
            ].copy()
        logging.debug(f"Initial profile data loaded. Rows: {len(self.profile_data)}")

        # 2. Check for Modified Data and OVERWRITE if present
        temp_dir = tempfile.gettempdir()
        date_string = self.date.strftime("%Y%m%d")

        # Format the profile data before saving
        if 'survey_unit' not in self.profile_data.columns:
            self.profile_data['survey_unit'] = self.survey_unit

        self.profile_data['profile'] = self.profile_data['reg_id']

        self.profile_data['date'] = self.date.strftime("%Y-%m-%d")
        self.profile_data['year'] = self.date.year
        self.profile_data['month'] = self.date.month

        profile_output_path = os.path.join(temp_dir, 'New_Profile_Data',
                                           f"{self.survey_unit}_{self.profile}{date_string}.pkl")
        if os.path.exists(profile_output_path):
            try:
                self.profile_data = pd.read_pickle(profile_output_path)
                logging.warning(f"Overwriting with modified data from {profile_output_path}")
                self.added_points_x.clear()
                self.added_points_y.clear()
            except Exception as e:
                logging.error(f"Failed to load pickled data from temp file: {e}")

        # 3. CRITICAL: ENSURE NUMERIC COERCION (Applied to whatever self.profile_data is currently holding)
        self.profile_data['chainage'] = pd.to_numeric(self.profile_data['chainage'], errors='coerce')

        # Consistent check for elevation
        elevation_col = None
        if 'elevation' in self.profile_data.columns:
            elevation_col = 'elevation'
        elif 'elevation_od' in self.profile_data.columns:
            # Create 'elevation' from 'elevation_od' for plotting consistency
            self.profile_data['elevation'] = self.profile_data['elevation_od']
            elevation_col = 'elevation'

        if elevation_col:
            # --- THIS LINE MUST EXECUTE ON THE FINAL DATA ---
            self.profile_data['elevation'] = pd.to_numeric(self.profile_data['elevation'], errors='coerce')
            logging.debug(f"Coerced 'chainage' and '{elevation_col}' to numeric. Data ready for plot.")
        else:
            logging.error("Profile data is missing required 'elevation' or 'elevation_od' column.")
            self.profile_data = pd.DataFrame()


        # 4. Load Master Profile Data
        profile_output_path = os.path.join(temp_dir, 'New_MP_Data',
                                           f"MASTER_{self.survey_unit}_{self.profile}_{date_string}.pkl")
        if not force_db_load and os.path.exists(profile_output_path):
            try:
                self.current_master_profiles = pd.read_pickle(profile_output_path)
                logging.warning(f"Overwriting with modified master profile data from {profile_output_path}")
            except Exception as e:
                logging.error(f"Failed to load pickled master profile data from temp file: {e}")
                self.current_master_profiles = pd.DataFrame()
        else:

            conn = establish_connection()
            if conn:
                # **FIX: Add ORDER BY sequence to preserve original order**
                master_profile_query = f"""
                    SELECT * FROM topo_qc.master_profiles 
                    WHERE profile_id = '{self.profile}'
                    ORDER BY sequence ASC
                """
                self.current_master_profiles = get_data(query=master_profile_query, conn=conn)
                conn.close()
                logging.info(
                    f"Master profile data loaded with order preserved. Rows: {len(self.current_master_profiles)}")
            else:
                self.current_master_profiles = pd.DataFrame()
                logging.warning("Skipping master profile load due to DB connection failure.")


        # 5. Run QA/QC on loaded profile
        try:
            self.profile_issues = qc_profile(self.current_master_profiles, self.profile_data)
        except:
            logging.error("Error occurred during profile QC.", exc_info=True)

        logging.info(self.profile_issues)

        # Intial CPA after deletion
        cpa_output_path = os.path.join(temp_dir, 'Calculated_CPA_Values',
                                       f"{self.survey_unit}_{self.profile}{self.date.strftime('%Y%m%d')}.pkl")

        os.makedirs(os.path.dirname(cpa_output_path), exist_ok=True)

        new_cpa_df = CalculateCPA(survey_unit=self.survey_unit, profile=self.profile,
                                  master_profile_data=self.current_master_profiles,
                                  new_profile_data=self.profile_data,
                                  survey_date=self.date)
        new_cpa_df.to_pickle(cpa_output_path)
        logging.info(f"CPA calculated and saved to {cpa_output_path}")


        # IMPORTANT push on loading a new profile to temp ONLY if not already present. We don't want to overwrite
        # user edits.
        temp_dir = tempfile.gettempdir()
        date_string = self.date.strftime("%Y%m%d")
        profile_output_path = os.path.join(temp_dir, 'New_Profile_Data',
                                           f"{self.survey_unit}_{self.profile}{date_string}.pkl")
        os.makedirs(os.path.dirname(profile_output_path), exist_ok=True)

        if not os.path.exists(profile_output_path):
            self.profile_data.to_pickle(profile_output_path)


        # Important - re-save the original MP data to temp if not already present
        temp_dir = tempfile.gettempdir()
        date_string = self.date.strftime("%Y%m%d")
        mp_profile_output_path = os.path.join(temp_dir, 'New_MP_Data',
                                              f"MASTER_{self.survey_unit}_{self.profile}_{date_string}.pkl")

        os.makedirs(os.path.dirname(mp_profile_output_path), exist_ok=True)

        if not os.path.exists(mp_profile_output_path):
            self.current_master_profiles.to_pickle(mp_profile_output_path)

    def check_temp_files_exist(self):
        """Check if temp files exist on users machine, we should clear them each time."""
        temp_dir = tempfile.gettempdir()
        temp_profile_output_dir = os.path.join(temp_dir, 'New_Profile_Data')
        temp_mp_output_dir = os.path.join(temp_dir, 'New_MP_Data')
        temp_cpa_output_dir = os.path.join(temp_dir, 'Calculated_CPA_Values')

        files_exist = all(os.path.exists(path) for path in [temp_profile_output_dir,temp_mp_output_dir,temp_cpa_output_dir])
        if files_exist:
            logging.info(f"Existing temporary files found!.")
        else:
            logging.info(f"No existing temporary files found")
        return files_exist

    def has_survey_been_marked_as_failed(self) -> bool:
        """
        Returns True if any 'check_status_enum' or 'issue_status_enum' column
        in topo_qc.qc_log has the value 'Failed' for this survey_unit and date.
        """
        conn = establish_connection()
        if conn is None:
            logging.error("Database connection failed in has_survey_been_marked_as_failed.")
            return False

        survey_unit = self.survey_unit
        date = self.date

        # Fetch all enum columns
        cols_query = text("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'topo_qc'
              AND table_name = 'qc_log'
              AND udt_name IN ('check_status_enum', 'issue_status_enum')
        """)
        cols_result = conn.execute(cols_query).fetchall()
        enum_columns = [r[0] for r in cols_result]

        if not enum_columns:
            logging.warning("No enum columns found in topo_qc.qc_log.")
            return False

        # Build dynamic WHERE clause to check any column = 'Failed'
        conditions = " OR ".join([f"{col} IN ('Failed', 'Rejected')" for col in enum_columns])


        query = text(f"""
            SELECT 1
            FROM topo_qc.qc_log
            WHERE survey_unit = :survey_unit
              AND completion_date = :date
              AND ({conditions})
            LIMIT 1
        """)

        result = conn.execute(query, {"survey_unit": survey_unit, "date": date}).fetchone()

        return bool(result)









    def check_if_database_push_completed(self):
        """
        Checks if the current survey (survey_unit + date) has already been pushed
        to the database by looking in the history tables.
        Returns True if a push exists, False otherwise.
        """
        conn = establish_connection()
        if conn is None:
            logging.error("Database connection failed in check_if_database_push_completed.")
            return False

        survey_unit = self.survey_unit
        date = self.date




        try:
            # Check topo_data history
            topo_result = conn.execute(
                text("""
                    SELECT 1
                    FROM topo_qc.topo_data_history
                    WHERE survey_unit = :survey_unit
                      AND date = :date
                    LIMIT 1
                """),
                {"survey_unit": survey_unit, "date": date}
            ).fetchone()

            if topo_result:
                logging.info(f"Survey {survey_unit} on {date} has already been pushed (found in topo_data_history).")
                return True

            # Optionally, also check master_profiles_history
            mp_result = conn.execute(
                text("""
                    SELECT 1
                    FROM topo_qc.master_profiles_history
                    WHERE date = :date
                      AND profile_id IN (
                          SELECT DISTINCT profile_id
                          FROM topo_qc.master_profiles
                          WHERE date = :date
                      )
                    LIMIT 1
                """),
                {"date": date}
            ).fetchone()

            if mp_result:
                logging.info(
                    f"Survey {survey_unit} on {date} has already been pushed (found in master_profiles_history).")
                return True

            # Optionally, check CPA history as well
            cpa_result = conn.execute(
                text("""
                    SELECT 1
                    FROM topo_qc.cpa_table_history
                    WHERE survey_unit = :survey_unit
                      AND date = :date
                    LIMIT 1
                """),
                {"survey_unit": survey_unit, "date": date}
            ).fetchone()

            if cpa_result:
                logging.info(f"Survey {survey_unit} on {date} has already been pushed (found in cpa_table_history).")
                return True

            return False  # No history found — survey not pushed yet

        except SQLAlchemyError as e:
            logging.error(f"Error checking database push: {e}")
            return False
        finally:
            conn.close()

    def clean_up_temp_files(self):
        """Safely remove all temporary output directories created during processing."""
        temp_dir = tempfile.gettempdir()
        temp_profile_output_dir = os.path.join(temp_dir, 'New_Profile_Data')
        temp_mp_output_dir = os.path.join(temp_dir, 'New_MP_Data')
        temp_cpa_output_dir = os.path.join(temp_dir, 'Calculated_CPA_Values')

        dirs_to_clean = [temp_profile_output_dir, temp_mp_output_dir, temp_cpa_output_dir]

        for directory in dirs_to_clean:
            if os.path.exists(directory):
                try:
                    shutil.rmtree(directory, ignore_errors=False)
                    print(f"✅ Removed {directory}")
                except PermissionError:
                    time.sleep(0.5)
                    try:
                        shutil.rmtree(directory, ignore_errors=False)
                        print(f"✅ Removed {directory} after retry")
                    except Exception as e:
                        print(f"⚠️ Failed to remove {directory}: {e}")
                        raise e
                except Exception as e:
                    print(f"⚠️ Unexpected cleanup error: {e}")
                    raise e

    def save_changes(self):
        """Saves changes to profile data and recalculates CPA."""



        # Check if any points were modified (added or dragged)
        has_modified_profile_data = (
                self.profile_data['chainage'].apply(lambda x: isinstance(x, (float, int))).any()
                or
                self.profile_data['elevation'].apply(lambda x: isinstance(x, (float, int))).any()

        )

        if not self.added_points_x and not has_modified_profile_data:
            logging.warning("Save called but no new points added or existing points dragged.")
            return

        logging.info(f"Saving changes for Profile: {self.profile}")
        self.edits_made = True

        # 1. Merge points into profile data (only if new points were added)
        if self.added_points_x:
            new_points = pd.DataFrame({
                'chainage': self.added_points_x,
                'elevation': self.added_points_y,
                'elevation_od': self.added_points_y,
                'fc' : 'ZZ',

            })

            # Round the numeric columns to 3 decimal places - Match Sands requirements
            new_points[['elevation', 'elevation_od']] = new_points[['elevation', 'elevation_od']].round(3)

            profile_data_with_points = pd.concat([self.profile_data.copy(), new_points], ignore_index=True)
            profile_data_with_points = profile_data_with_points.sort_values('chainage')

            # Need to add easting and northing and zz

            profile_data_with_points_eastings_northings = calculate_missing_northing_easting(profile_data_with_points.copy(), self.date, self.survey_unit)


            self.profile_data = profile_data_with_points_eastings_northings.copy()

            # 2. Clear temporary lists
            self.added_points_x.clear()
            self.added_points_y.clear()
            logging.info('New points merged and internal data updated.')






        # 3. Save modified profile data to temp directory
        temp_dir = tempfile.gettempdir()
        date_string = self.date.strftime("%Y%m%d")
        profile_output_path = os.path.join(temp_dir, 'New_Profile_Data',
                                           f"{self.survey_unit}_{self.profile}{date_string}.pkl")

        os.makedirs(os.path.dirname(profile_output_path), exist_ok=True)

        self.profile_data.to_pickle(profile_output_path)
        self.modified_profiles[self.profile] = profile_output_path
        logging.info(f"Modified profile data saved to temporary location: {profile_output_path}")

        if self.current_master_profiles is not None and not self.current_master_profiles.empty:

            # Ensure the data is coerced to numeric before saving
            self.current_master_profiles['chainage'] = pd.to_numeric(
                self.current_master_profiles['chainage'], errors='coerce'
            )
            if 'elevation' in self.current_master_profiles.columns:
                self.current_master_profiles['elevation'] = pd.to_numeric(
                    self.current_master_profiles['elevation'], errors='coerce'
                )

            # **FIX: Add sequence column to preserve order before saving**
            if 'sequence' not in self.current_master_profiles.columns:
                self.current_master_profiles['sequence'] = range(len(self.current_master_profiles))
            else:
                # Reset sequence to reflect current order
                self.current_master_profiles['sequence'] = range(len(self.current_master_profiles))

            master_output_path = os.path.join(temp_dir, 'New_MP_Data',
                                              f"MASTER_{self.survey_unit}_{self.profile}_{self.date.strftime('%Y%m%d')}.pkl")
            os.makedirs(os.path.dirname(master_output_path), exist_ok=True)
            self.current_master_profiles.to_pickle(master_output_path)
            logging.info(f"Modified master profile data saved to temporary location: {master_output_path}")

        # 4. Recalculate CPA

        cpa_output_path = os.path.join(temp_dir, 'Calculated_CPA_Values',
                                       f"{self.survey_unit}_{self.profile}{self.date.strftime('%Y%m%d')}.pkl")

        os.makedirs(os.path.dirname(cpa_output_path ), exist_ok=True)

        new_cpa_df = CalculateCPA(survey_unit=self.survey_unit, profile=self.profile,
                                  master_profile_data=self.current_master_profiles,
                                  new_profile_data=self.profile_data,
                                  survey_date=self.date
                                  )
        new_cpa_df.to_pickle(cpa_output_path)
        logging.info(f"CPA calculated and saved to {cpa_output_path}")
        # 5. Run QA/QC on loaded profile
        try:
            self.profile_issues = qc_profile(self.current_master_profiles, self.profile_data)
        except:
            logging.error("Error occurred during profile QC.", exc_info=True)

    def delete_changes(self):
        """Removes modified profile data from temp storage and resets current data."""
        logging.info(f"Deleting changes for Profile: {self.profile}")

        if self.flagged_profiles and self.profile in self.flagged_reasons.keys():

            self.flagged_profiles = False
            self.flagged_reasons.pop(self.profile)




        # 1. Remove temp Profile file
        temp_dir = tempfile.gettempdir()
        date_string = self.date.strftime("%Y%m%d")
        profile_output_path = os.path.join(temp_dir, 'New_Profile_Data',
                                           f"{self.survey_unit}_{self.profile}{date_string}.pkl")

        if os.path.exists(profile_output_path):
            os.remove(profile_output_path)
            logging.warning(f"Deleted modified profile data file at {profile_output_path}")
        else:
            logging.debug("No temporary modified file found to delete.")

        # 2. Remove temp MP Profile file
        mp_output_path = os.path.join(temp_dir, 'New_MP_Data',
                                      f"MASTER_{self.survey_unit}_{self.profile}_{date_string}.pkl")

        if os.path.exists(mp_output_path):
            os.remove(mp_output_path)
            logging.warning(f"Deleted master profile data file at {mp_output_path}")
        else:
            logging.debug(f"No temporary modified file found to delete: {mp_output_path}")

        # 3. Reset profile data to original
        current_profile_value = str(self.unique_profiles.iloc[self.current_index]['reg_id']).strip()
        self.profile_data = self.new_survey_topo_data[
            self.new_survey_topo_data['reg_id'] == current_profile_value
            ].copy()



        # 4. Reset master profile data
        conn = establish_connection()
        if conn:
            master_profile_query = f"SELECT * FROM topo_qc.master_profiles WHERE profile_id = '{self.profile}'"
            self.current_master_profiles = get_data(query=master_profile_query, conn=conn)
            conn.close()
            logging.info(f"Master profile data loaded. Rows: {len(self.current_master_profiles)}")
        else:
            self.current_master_profiles = pd.DataFrame()
            logging.warning("Skipping master profile load due to DB connection failure.")

        # 5. Reset temporary added points
        self.added_points_x.clear()
        self.added_points_y.clear()

        # 6.. Re-apply numeric conversions
        self.profile_data['chainage'] = pd.to_numeric(self.profile_data['chainage'], errors='coerce')

        # 7. Ensure 'elevation' column exists before trying to coerce it
        if 'elevation' in self.profile_data.columns:
            self.profile_data['elevation'] = pd.to_numeric(self.profile_data['elevation'], errors='coerce')
        elif 'elevation_od' in self.profile_data.columns:
            self.profile_data['elevation'] = pd.to_numeric(self.profile_data['elevation_od'], errors='coerce')

        # 8. Important - re-save the original data to temp if not already present
        temp_dir = tempfile.gettempdir()
        date_string = self.date.strftime("%Y%m%d")
        profile_output_path = os.path.join(temp_dir, 'New_Profile_Data',
                                           f"{self.survey_unit}_{self.profile}{date_string}.pkl")
        os.makedirs(os.path.dirname(profile_output_path), exist_ok=True)

        if not os.path.exists(profile_output_path):
            self.profile_data.to_pickle(profile_output_path)


        # 9. Important - re-save the original MP data to temp if not already present
        temp_dir = tempfile.gettempdir()
        date_string = self.date.strftime("%Y%m%d")
        mp_profile_output_path = os.path.join(temp_dir, 'New_MP_Data',
                                           f"MASTER_{self.survey_unit}_{self.profile}_{date_string}.pkl")
        os.makedirs(os.path.dirname(mp_profile_output_path), exist_ok=True)

        if not os.path.exists(mp_profile_output_path) :
            self.current_master_profiles.to_pickle(mp_profile_output_path )


        # 10. Recalculate CPA after deletion
        cpa_output_path = os.path.join(temp_dir, 'Calculated_CPA_Values',
                                       f"{self.survey_unit}_{self.profile}{self.date.strftime('%Y%m%d')}.pkl")

        os.makedirs(os.path.dirname(cpa_output_path), exist_ok=True)

        new_cpa_df = CalculateCPA(survey_unit=self.survey_unit, profile=self.profile,
                                  master_profile_data=self.current_master_profiles,
                                  new_profile_data=self.profile_data,
                                  survey_date=self.date
                                  )
        new_cpa_df.to_pickle(cpa_output_path)
        logging.info(f"CPA calculated and saved to {cpa_output_path}")

        self.edits_made = False

        logging.debug("Profile data reset to original and coerced.")

        try:
            self.profile_issues = qc_profile(self.current_master_profiles, self.profile_data)
        except:
            logging.error("Error occurred during profile QC.", exc_info=True)

    def log_index(self):
        """Logs the current session state."""
        now = datetime.now()
        current_date_time_str = now.strftime("%Y-%m-%d-%H-%M-%S")
        log_data = {'Survey_Unit': [self.survey_unit], 'Profile': [self.profile], 'Date': [self.date],
                    'Last Session Date': [current_date_time_str]}
        lof_df = pd.DataFrame.from_dict(log_data)
        lof_df.to_pickle(self.LAST_SESSION_LOG)
        logging.info(f"Session index logged. Current state: {self.survey_unit}, {self.profile}")

    def end_session(self):
        """Logs the final state and quits."""
        if getattr(self, "edits_made", False):
            reply = QMessageBox.warning(
                None,
                "Unpushed Edits Detected",
                "⚠️ You have unpushed edits that haven't been saved or pushed yet. All edit will be lost if the session is\n"
                " turned off.\n\n"
                "Do you want to end the session anyway?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if reply == QMessageBox.No:
                logging.info("End Session cancelled by user due to unpushed edits.")
                return  # Abort the quit process

        logging.critical("End Session requested. Logging final state and exiting.")
        self.clean_up_temp_files()
        self.log_index()

    def end_session_and_push(self):
        """Logs the final state, pushes changes to DB, and quits."""
        temp_dir = tempfile.gettempdir()
        temp_profile_output_dir = os.path.join(temp_dir, 'New_Profile_Data')
        temp_mp_output_dir = os.path.join(temp_dir, 'New_MP_Data')
        temp_cpa_output_dir = os.path.join(temp_dir, 'Calculated_CPA_Values')





        # 1) Check if temp files exist
        if not self.check_temp_files_exist():
            QMessageBox.information(
                None,
                "No Changes to Push",
                "There are no temp files to push. Temporary files not found.",
                QMessageBox.Ok
            )
            logging.info("Push requested but no temporary files found. Aborting push.")
            return

        # 2) Push data from directories
        dirs_to_push = [temp_profile_output_dir, temp_mp_output_dir, temp_cpa_output_dir]

        for directory in dirs_to_push:
            if not os.path.exists(directory):
                logging.info(f"Directory not found: {directory}")
                continue

            file_paths = [
                os.path.join(directory, f)
                for f in os.listdir(directory)
                if os.path.isfile(os.path.join(directory, f))
            ]

            if not file_paths:
                logging.info(f"No files found in {directory}")
                continue

            logging.info(f"Files to push from {directory}: {file_paths}")

            conn = establish_connection()
            if conn is None:
                QMessageBox.critical(
                    None,
                    "Database Connection Failed",
                    "Could not connect to the database. Push aborted.",
                    QMessageBox.Ok
                )
                logging.error("Push aborted due to failed DB connection.")
                return

            try:
                if 'New_MP_Data' in directory:
                    self.updateMpDatabase(conn, file_paths)

                elif 'Calculated_CPA_Values' in directory:
                    self.updateCpaDatabase(conn, file_paths)

                elif 'New_Profile_Data' in directory:
                   self.updateTopoDatabase(conn, file_paths)



            finally:
                conn.close()

        # 3) Clean up temp files
        self.clean_up_temp_files()

        conn = establish_connection()
        if conn is None:
            QMessageBox.critical(
                None,
                "Database Connection Failed",
                "Could not connect to the database. Push aborted.",
                QMessageBox.Ok
            )
            logging.error("Push aborted due to failed DB connection.")
            return


        self.updateQClogDatabase(conn)

        # 4) Reload after a short delay
        QTimer.singleShot(300, lambda: self._reload_after_cleanup())

    def prepare_sands_ready_files(self):
        pass

    def mark_survey_as_rejected(self):
        try:
            conn = establish_connection()
            if conn is None:
                QMessageBox.critical(
                    None,
                    "Database Connection Failed",
                    "Could not connect to the database. Operation aborted.",
                    QMessageBox.Ok
                )
                logging.error("Operation aborted due to failed DB connection.")
                return

            issue_map = {
                "Excessive Over Spacing": ["checks_pl_point_spacing", "checks_pl_point_spacing_c"],
                "Survey Does Not Reach Master Profile Landward Limit": [
                    "checks_pl_profile_start_position",
                    "checks_pl_profile_start_position_c"
                ],
                "Survey Does Not Reach Seaward Limit": [
                    "checks_pl_seaward_limit",
                    "checks_pl_seaward_limit_c"
                ],
            }

            # Get lists of profiles by flag reason
            flagged = self.flagged_reasons  # e.g. {"Profile1": "Excessive Over Spacing", ...}

            all_excessive = [k for k, v in flagged.items() if v == "Excessive Over Spacing"]
            all_landward = [k for k, v in flagged.items() if v == "Survey Does Not Reach Master Profile Landward Limit"]
            all_seaward = [k for k, v in flagged.items() if v == "Survey Does Not Reach Seaward Limit"]

            def perform_update(issue_key, profiles):
                """Helper to run update for a given issue type."""
                db_field, db_field_c = issue_map[issue_key]
                profiles_str = ", ".join(profiles)

                update_query = text(f"""
                    UPDATE topo_qc.qc_log
                    SET {db_field} = 'Failed',
                        {db_field_c} = :reason
                    WHERE survey_unit = :survey_unit
                    AND completion_date = :date;
                """)

                conn.execute(update_query, {
                    "reason": f"{issue_key}: {profiles_str}",
                    "survey_unit": self.survey_unit,
                    "date": self.date
                })
                logging.info(f"Updated {issue_key} profiles: {profiles_str}")

            # Run updates for each issue category
            if all_excessive:
                perform_update("Excessive Over Spacing", all_excessive)
            if all_landward:
                perform_update("Survey Does Not Reach Master Profile Landward Limit", all_landward)
            if all_seaward:
                perform_update("Survey Does Not Reach Seaward Limit", all_seaward)

            conn.commit()  # ✅ commit the updates
            conn.close()

            QMessageBox.information(
                None,
                "Survey Fields Marked as Failed",
                "Survey successfully set with failures in the database. Admin will be notified.",
                QMessageBox.Ok
            )
            logging.info("Survey marked as Failed successfully.")

        except Exception as e:
            logging.error(f"Failed to mark survey as failed: {e}")
            QMessageBox.critical(
                None,
                "Database Error",
                f"Could not mark survey as failed.\nError: {e}",
                QMessageBox.Ok
            )


    def undo_last_push(self):
        """Undo the most recent database changes for both MP and CPA."""

        conn = establish_connection()

        if conn is None:
            QMessageBox.critical(
                None,
                "Database Connection Failed",
                "Could not connect to the database. Undo aborted.",
                QMessageBox.Ok
            )
            logging.error("Undo aborted due to failed DB connection.")
            return

        try:
            self.undoMpDatabase(conn)
            self.undoCpaDatabase(conn)
            self.undoTopoDatabase(conn)
            self.undoQcLogFlags(conn)


        finally:
            conn.close()

        self.clean_up_temp_files()
        QTimer.singleShot(300, lambda: self._reload_after_cleanup())

    # -----------------------------
    #   Master Profile Updates
    # -----------------------------

    #TODO - Add method that undoes the last QC log changes

    def updateMpDatabase(self, conn, file_paths):
        """Updates the master profiles in the database with new data from temp files."""
        try:
            new_master_profile_dfs = [pd.read_pickle(fp) for fp in file_paths]
            all_new_mp_data = pd.concat(new_master_profile_dfs, ignore_index=True)
            all_new_mp_data.columns = all_new_mp_data.columns.str.lower()

            profile_ids = all_new_mp_data['profile_id'].unique().tolist()
            if not profile_ids:
                logging.info("No profiles to update.")
                return

            # **FIX: Ensure sequence column exists and is properly set**
            if 'sequence' not in all_new_mp_data.columns:
                logging.warning("Sequence column missing! Adding default sequence per profile.")
                # Group by profile_id and add sequence within each group
                all_new_mp_data['sequence'] = all_new_mp_data.groupby('profile_id').cumcount()

            user_name = settings.get("user")

            with conn.begin():
                conn.execute(text("LOCK TABLE topo_qc.master_profiles IN EXCLUSIVE MODE"))
                conn.execute(text("LOCK TABLE topo_qc.master_profiles_history IN EXCLUSIVE MODE"))

                # Backup current rows (including sequence)
                backup_query = text("""
                    INSERT INTO topo_qc.master_profiles_history (
                        profile_id, date, chainage, elevation, sequence, changed_at, user_name
                    )
                    SELECT profile_id, date, chainage, elevation, sequence, now(), :user_name
                    FROM topo_qc.master_profiles
                    WHERE profile_id = ANY(:ids)
                """)
                conn.execute(backup_query, {"ids": profile_ids, "user_name": user_name})

                # Delete old and insert new
                conn.execute(text("DELETE FROM topo_qc.master_profiles WHERE profile_id = ANY(:ids)"),
                             {"ids": profile_ids})

                # **FIX: Include sequence in the insert**
                insert_data = all_new_mp_data[['profile_id', 'date', 'chainage', 'elevation', 'sequence']].to_dict(
                    orient='records')
                insert_query = text("""
                    INSERT INTO topo_qc.master_profiles (profile_id, date, chainage, elevation, sequence)
                    VALUES (:profile_id, :date, :chainage, :elevation, :sequence)
                """)
                conn.execute(insert_query, insert_data)

            logging.info("Master profiles updated successfully with preserved order.")

        except SQLAlchemyError as e:
            logging.error(f"Failed to update master profiles: {e}")
            QMessageBox.critical(None, "Database Error",
                                 f"Could not update master profiles.\nError: {e}", QMessageBox.Ok)

    def updateCpaDatabase(self, conn, file_paths):
        """Updates the CPA values in the database with new data from temp files."""
        user_name = settings.get("user")

        try:
            new_cpa_dfs = [pd.read_pickle(fp) for fp in file_paths]
            all_new_cpa_data = pd.concat(new_cpa_dfs, ignore_index=True)
            all_new_cpa_data.columns = all_new_cpa_data.columns.str.lower()



            if len(all_new_cpa_data.columns) <= 0:
                logging.error("CPA Error: No data to push.")
                QMessageBox.critical(None, "CPA Error:",
                                     "No Data to push was found.", QMessageBox.Ok)
                return

            survey_unit =self.survey_unit
            date = self.date

            with conn.begin():
                conn.execute(text("LOCK TABLE topo_qc.cpa_table IN EXCLUSIVE MODE"))
                conn.execute(text("LOCK TABLE topo_qc.cpa_table_history IN EXCLUSIVE MODE"))

                # Backup existing records
                backup_query = text("""
                    INSERT INTO topo_qc.cpa_table_history (
                        survey_unit, date, profile, area, changed_at, user_name
                    )
                    SELECT survey_unit, date, profile, area, now(), :user_name
                    FROM topo_qc.cpa_table
                    WHERE survey_unit = :survey_unit AND date = :date
                """)
                conn.execute(backup_query, {"survey_unit": survey_unit, "date": date, "user_name": user_name})

                # Delete old and insert new
                conn.execute(text("DELETE FROM topo_qc.cpa_table WHERE survey_unit = :survey_unit AND date = :date"),
                             {"survey_unit": survey_unit, "date": date})

                insert_data = all_new_cpa_data.to_dict(orient='records')
                insert_query = text("""
                    INSERT INTO topo_qc.cpa_table (survey_unit, date, profile, area)
                    VALUES (:survey_unit, :date, :profile, :area)
                """)
                conn.execute(insert_query, insert_data)

            logging.info("CPA values updated successfully.")

        except SQLAlchemyError as e:
            logging.error(f"Failed to update CPA values: {e}")
            QMessageBox.critical(None, "Database Error",
                                 f"Could not update CPA values.\nError: {e}", QMessageBox.Ok)

    def updateTopoDatabase(self, conn, file_paths):
        """Updates the topo_data table with new data from temp files and stores a history backup."""
        user_name = settings.get("user")

        try:
            # Load new topo data
            new_topo_dfs = [pd.read_pickle(fp) for fp in file_paths]
            all_new_topo_data = pd.concat(new_topo_dfs, ignore_index=True)
            all_new_topo_data.columns = all_new_topo_data.columns.str.lower()

            if all_new_topo_data.empty:
                logging.info("No Topo data to update.")
                return

            survey_unit = self.survey_unit
            date = self.date

            with conn.begin():  # Transactional block
                # Backup current rows to history
                backup_query = text("""
                    INSERT INTO topo_qc.topo_data_history (
                        easting, northing, elevation_od, chainage, fc,
                        profile, reg_id, survey_unit, date, year, month, changed_at, user_name
                    )
                    SELECT easting, northing, elevation_od, chainage, fc,
                           profile, reg_id, survey_unit, date, year, month, now(), :user_name
                    FROM topo_qc.topo_data
                    WHERE survey_unit = :survey_unit AND date = :date
                """)
                conn.execute(backup_query, {"survey_unit": survey_unit, "date": date, "user_name": user_name})

                # Delete old rows
                delete_query = text("""
                    DELETE FROM topo_qc.topo_data
                    WHERE survey_unit = :survey_unit AND date = :date
                """)
                conn.execute(delete_query, {"survey_unit": survey_unit, "date": date})

                # Prepare new data for insertion
                # Prepare new data for insertion
                insert_data = all_new_topo_data.to_dict(orient='records')

                for record in insert_data:
                    # Rename 'elevation' -> 'elevation_od' if needed
                    if "elevation" in record:
                        record["elevation_od"] = record.pop("elevation")

                    # Fix missing or NaN survey_unit/date/year/month
                    # survey_unit is usually a string
                    if pd.isna(record.get("survey_unit")):
                        record["survey_unit"] = self.survey_unit  # fallback

                    # date must be a proper date object
                    if pd.isna(record.get("date")):
                        record["date"] = self.date  # fallback

                    # year and month must be integers
                    if pd.isna(record.get("year")):
                        record["year"] = int(pd.to_datetime(record["date"]).year)
                    if pd.isna(record.get("month")):
                        record["month"] = int(pd.to_datetime(record["date"]).month)

                # Bulk insert new rows
                insert_query = text("""
                    INSERT INTO topo_qc.topo_data (
                        easting, northing, elevation_od, chainage, fc,
                        profile, reg_id, survey_unit, date, year, month
                    )
                    VALUES (:easting, :northing, :elevation_od, :chainage, :fc,
                            :profile, :reg_id, :survey_unit, :date, :year, :month)
                """)
                conn.execute(insert_query, insert_data)

            logging.info("Topo data updated successfully.")

        except SQLAlchemyError as e:
            logging.error(f"Failed to update topo_data: {e}")
            QMessageBox.critical(
                None,
                "Database Error",
                f"Could not update topo_data.\nError: {e}",
                QMessageBox.Ok
            )

    def updateQClogDatabase(self, conn):
        """Updates the QC log with identified profile issues."""
        try:
            survey_unit = self.survey_unit
            date = self.date

            # check no profile issues if there are issues find the find any of the columns not flagged yet
            # and then update them to ommitted
            flagged = self.flagged_reasons
            if  self.profile_issues:
                all_excessive = [k for k, v in flagged.items() if v == "Excessive Over Spacing"]
                all_landward = [k for k, v in flagged.items() if
                                v == "Survey Does Not Reach Master Profile Landward Limit"]
                all_seaward = [k for k, v in flagged.items() if v == "Survey Does Not Reach Seaward Limit"]

                db_fields_to_update = []
                db_fields_c_to_update = []

                if not all_excessive:
                    db_fields_to_update.append("checks_pl_point_spacing")
                    db_fields_c_to_update.append("checks_pl_point_spacing_c")
                if not all_landward:
                    db_fields_to_update.append("checks_pl_profile_start_position")
                    db_fields_c_to_update.append("checks_pl_profile_start_position_c")
                if not all_seaward:
                    db_fields_to_update.append("checks_pl_seaward_limit")
                    db_fields_c_to_update.append("checks_pl_seaward_limit_c")

                for db_field, db_field_c in zip(db_fields_to_update, db_fields_c_to_update):

                    check_if_existing_issue_query = text(f"""
                        SELECT {db_field}
                        FROM topo_qc.qc_log
                        WHERE survey_unit = :survey_unit
                        AND completion_date = :date;
                    """)
                    result = conn.execute(check_if_existing_issue_query, {
                        "survey_unit": survey_unit,
                        "date": date
                    })
                    existing_value = result.scalar()
                    if existing_value == 'Issue':
                        update_query = text(f"""
                                               UPDATE topo_qc.qc_log
                                               SET {db_field} = 'Resolved',
                                                   {db_field_c} = 'Fixed by Profile Viewer Tool'
                                               WHERE survey_unit = :survey_unit
                                               AND completion_date = :date;
                                           """)
                        conn.execute(update_query, {
                            "survey_unit": survey_unit,
                            "date": date
                        })
                        logging.info(f"Updated QC log field {db_field} to Resolved.")
                    else:
                        update_query = text(f"""
                                              UPDATE topo_qc.qc_log
                                              SET {db_field} = 'Pass',
                                                  {db_field_c} = 'Reviewed by Profile Viewer Tool'
                                              WHERE survey_unit = :survey_unit
                                              AND completion_date = :date;
                                          """)
                        conn.execute(update_query, {
                            "survey_unit": survey_unit,
                            "date": date
                        })
                        logging.info(f"Updated QC log field {db_field} to Pass.")

            conn.commit()  # ✅ commit the updates
            logging.info("QC log updated successfully.")
        except SQLAlchemyError as e:
            logging.error(f"Failed to update QC log: {e}")
            QMessageBox.critical(None, "Database Error",
                                 f"Could not update QC log.\nError: {e}", QMessageBox.Ok)

    def undoMpDatabase(self, conn):
        """Undo the most recent Master Profile push for the current user."""
        user_name = settings.get("user")

        try:
            with conn.begin():
                conn.execute(text("LOCK TABLE topo_qc.master_profiles IN EXCLUSIVE MODE"))
                conn.execute(text("LOCK TABLE topo_qc.master_profiles_history IN EXCLUSIVE MODE"))

                # Find the latest change timestamp
                result = conn.execute(
                    text("""
                        SELECT MAX(changed_at) AS last_change
                        FROM topo_qc.master_profiles_history
                        WHERE user_name = :user_name
                    """),
                    {"user_name": user_name}
                )
                last_change = result.scalar()

                if not last_change:
                    QMessageBox.information(None, "No Changes to Undo",
                                            "No Master Profile changes found in history.", QMessageBox.Ok)
                    logging.info("No Master Profile changes found in history.")
                    return

                logging.info(f"Undoing Master Profile changes from {last_change}")

                # Get affected profile_ids
                result = conn.execute(
                    text("""
                        SELECT DISTINCT profile_id
                        FROM topo_qc.master_profiles_history
                        WHERE changed_at = :last_change AND user_name = :user_name
                    """),
                    {"last_change": last_change, "user_name": user_name}
                )
                profile_ids = [r[0] for r in result.fetchall()]

                if not profile_ids:
                    QMessageBox.information(None, "No Profiles Found",
                                            "No profiles found for this change.", QMessageBox.Ok)
                    return

                # Restore previous state
                delete_query = text("DELETE FROM topo_qc.master_profiles WHERE profile_id = ANY(:ids)")
                conn.execute(delete_query, {"ids": profile_ids})

                # **FIX: Include sequence column in restore**
                insert_from_history = text("""
                    INSERT INTO topo_qc.master_profiles (profile_id, date, chainage, elevation, sequence)
                    SELECT profile_id, date, chainage, elevation, sequence
                    FROM topo_qc.master_profiles_history
                    WHERE profile_id = ANY(:ids)
                    AND changed_at = :last_change
                    AND user_name = :user_name
                    ORDER BY sequence ASC
                """)
                conn.execute(insert_from_history,
                             {"ids": profile_ids, "last_change": last_change, "user_name": user_name})

                # Optional: clean up the restored history entries
                conn.execute(
                    text("""
                        DELETE FROM topo_qc.master_profiles_history
                        WHERE profile_id = ANY(:ids)
                        AND changed_at = :last_change
                        AND user_name = :user_name
                    """),
                    {"ids": profile_ids, "last_change": last_change, "user_name": user_name}
                )

                logging.info("Undo successful: Master Profiles restored to previous state with preserved order.")

        except SQLAlchemyError as e:
            logging.error(f"Failed to undo Master Profiles: {e}")
            QMessageBox.critical(None, "Database Error",
                                 f"Could not undo last Master Profile push.\nError: {e}", QMessageBox.Ok)

    def undoCpaDatabase(self, conn):
        """Undo the most recent CPA push for the current user."""
        user_name = settings.get("user")

        try:
            with conn.begin():
                conn.execute(text("LOCK TABLE topo_qc.cpa_table IN EXCLUSIVE MODE"))
                conn.execute(text("LOCK TABLE topo_qc.cpa_table_history IN EXCLUSIVE MODE"))

                # Find the latest change timestamp
                result = conn.execute(
                    text("""
                        SELECT MAX(changed_at) AS last_change
                        FROM topo_qc.cpa_table_history
                        WHERE user_name = :user_name
                    """),
                    {"user_name": user_name}
                )
                last_change = result.scalar()

                if not last_change:
                    QMessageBox.information(None, "No Changes to Undo",
                                            "No CPA changes found in history.", QMessageBox.Ok)
                    logging.info("No CPA changes found in history.")
                    return

                logging.info(f"Undoing CPA changes from {last_change}")

                # Get affected survey_unit + date pairs
                result = conn.execute(
                    text("""
                        SELECT DISTINCT survey_unit, date
                        FROM topo_qc.cpa_table_history
                        WHERE changed_at = :last_change AND user_name = :user_name
                    """),
                    {"last_change": last_change, "user_name": user_name}
                )
                rows = result.fetchall()
                if not rows:
                    QMessageBox.information(None, "No CPA Changes Found",
                                            "No CPA entries found for this change.", QMessageBox.Ok)
                    return

                for survey_unit, date in rows:
                    # Delete current records
                    conn.execute(
                        text("DELETE FROM topo_qc.cpa_table WHERE survey_unit = :su AND date = :dt"),
                        {"su": survey_unit, "dt": date}
                    )

                    # Restore from history
                    conn.execute(
                        text("""
                            INSERT INTO topo_qc.cpa_table (survey_unit, date, profile, area)
                            SELECT survey_unit, date, profile, area
                            FROM topo_qc.cpa_table_history
                            WHERE survey_unit = :su AND date = :dt
                            AND changed_at = :last_change
                            AND user_name = :user_name
                        """),
                        {"su": survey_unit, "dt": date, "last_change": last_change, "user_name": user_name}
                    )

                    # Optional cleanup of restored entries
                    conn.execute(
                        text("""
                            DELETE FROM topo_qc.cpa_table_history
                            WHERE survey_unit = :su AND date = :dt
                            AND changed_at = :last_change
                            AND user_name = :user_name
                        """),
                        {"su": survey_unit, "dt": date, "last_change": last_change, "user_name": user_name}
                    )

                logging.info("Undo successful: CPA table restored to previous state.")

        except SQLAlchemyError as e:
            logging.error(f"Failed to undo CPA data: {e}")
            QMessageBox.critical(None, "Database Error",
                                 f"Could not undo last CPA push.\nError: {e}", QMessageBox.Ok)

    def undoTopoDatabase(self, conn):
        """Undo the most recent topo_data push for the current user."""
        user_name = settings.get("user")

        try:
            with conn.begin():
                conn.execute(text("LOCK TABLE topo_qc.topo_data IN EXCLUSIVE MODE"))
                conn.execute(text("LOCK TABLE topo_qc.topo_data_history IN EXCLUSIVE MODE"))

                # Get latest change timestamp
                result = conn.execute(text("""
                    SELECT MAX(changed_at) AS last_change
                    FROM topo_qc.topo_data_history
                    WHERE user_name = :user_name
                """), {"user_name": user_name})
                last_change = result.scalar()

                if not last_change:
                    QMessageBox.information(None, "No Changes to Undo",
                                            "No Topo data changes found in history.", QMessageBox.Ok)
                    logging.info("No Topo data changes found in history.")
                    return

                logging.info(f"Undoing Topo data changes from {last_change}")

                # Get affected survey_unit/date pairs
                result = conn.execute(text("""
                    SELECT DISTINCT survey_unit, date
                    FROM topo_qc.topo_data_history
                    WHERE changed_at = :last_change AND user_name = :user_name
                """), {"last_change": last_change, "user_name": user_name})
                rows = result.fetchall()

                if not rows:
                    QMessageBox.information(None, "No Topo Entries Found",
                                            "No topo_data entries found for this change.", QMessageBox.Ok)
                    return

                for survey_unit, date in rows:
                    # Delete current topo_data
                    conn.execute(text("""
                        DELETE FROM topo_qc.topo_data
                        WHERE survey_unit = :su AND date = :dt
                    """), {"su": survey_unit, "dt": date})

                    # Restore from history
                    conn.execute(text("""
                        INSERT INTO topo_qc.topo_data (
                            easting, northing, elevation_od, chainage, fc,
                            profile, reg_id, survey_unit, date, year, month
                        )
                        SELECT easting, northing, elevation_od, chainage, fc,
                               profile, reg_id, survey_unit, date, year, month
                        FROM topo_qc.topo_data_history
                        WHERE survey_unit = :su AND date = :dt
                          AND changed_at = :last_change
                          AND user_name = :user_name
                    """), {"su": survey_unit, "dt": date,
                           "last_change": last_change, "user_name": user_name})

                    # Optional cleanup
                    conn.execute(text("""
                        DELETE FROM topo_qc.topo_data_history
                        WHERE survey_unit = :su AND date = :dt
                          AND changed_at = :last_change
                          AND user_name = :user_name
                    """), {"su": survey_unit, "dt": date,
                           "last_change": last_change, "user_name": user_name})

                logging.info("Undo successful: Topo data restored to previous state.")

        except SQLAlchemyError as e:
            logging.error(f"Failed to undo topo_data: {e}")
            QMessageBox.critical(None, "Database Error",
                                 f"Could not undo last topo_data push.\nError: {e}", QMessageBox.Ok)

    def undoQcLogFlags(self, conn):
        """
        NOT USED
        Undo QC log flags for the flagged profiles in the current survey."""

        date = self.date
        survey_unit = self.survey_unit

        try:
            with conn.begin():
                conn.execute(text("LOCK TABLE topo_qc.qc_log IN EXCLUSIVE MODE"))

                get_survey_id = text("""
                    SELECT survey_id FROM topo_qc.qc_log WHERE survey_unit = :survey_unit AND completion_date = :date;
                """)
                result = conn.execute(get_survey_id, {
                    "survey_unit": survey_unit,
                    "date": date
                })
                row = result.fetchone()
                if not row:
                    logging.info("No QC log entry found for this survey unit and date.")
                    return

                survey_id = row[0]

                history_result= conn.execute(
                    text("""
                        SELECT * FROM topo_qc.topo_issue_history WHERE survey_id = :survey_id AND new_issue_status = 'Failed'
                        ORDER BY updated_at DESC LIMIT 1
                    """),
                    {"survey_id": survey_id}
                )
                history_row = history_result.mappings().first()

                if not history_row:
                    logging.info("No rejected issue history found to undo.")
                    return

                unflag_field = history_row['issue_field']


                old_issue_comment  = history_row['old_issue_comment']


                update_query = text(f"""
                    UPDATE topo_qc.qc_log
                    SET {unflag_field} = 'Issue',
                        {unflag_field}_c = :old_comment
                    WHERE survey_id = :survey_id
                """)
                conn.execute(update_query, {
                    "survey_id": survey_id,

                    "old_comment": old_issue_comment
                })
                logging.info(f"Unflagged QC log field {unflag_field} to Omitted.")

        except SQLAlchemyError as e:
            logging.error(f"Failed to undo QC log flags: {e}")
            QMessageBox.critical(None, "Database Error",
                                 f"Could not undo QC log flags.\nError: {e}", QMessageBox.Ok)

    def _reload_after_cleanup(self):
        """Continuation after cleanup delay."""
        self.load_current_profile(force_db_load=True)

# --- NEW DRAGGING LOGIC CLASS ---
class DraggablePoints:
    """A helper class to manage Matplotlib events for dragging scatter points."""

    lock = None  # Class-wide lock to prevent multiple points being dragged at once

    def __init__(self, app_window, target_artist, drag_target='survey'):
        self.app = app_window
        self.data_h = app_window.data_handler
        self.canvas = app_window.canvas_widget
        self.ax = app_window.ax
        self.scatter_artist = target_artist

        self.selected_index = None
        self.offset = (0, 0)
        self.is_main_profile_data = drag_target

        # Connect Matplotlib events
        self.cid_press = self.canvas.mpl_connect('button_press_event', self.on_press)
        self.cid_move = self.canvas.mpl_connect('motion_notify_event', self.on_move)
        self.cid_release = self.canvas.mpl_connect('button_release_event', self.on_release)

        logging.info(f"Drag Mode enabled. Target: {'Main Profile' if self.is_main_profile_data else 'Added Points'}")

    def disconnect(self):
        """Disconnects all event handlers."""
        try:
            self.canvas.mpl_disconnect(self.cid_press)
            self.canvas.mpl_disconnect(self.cid_move)
            self.canvas.mpl_disconnect(self.cid_release)
            logging.info("Drag Mode disabled. Events disconnected.")
        except Exception as e:
            logging.warning(f"Error disconnecting drag events (canvas may be cleared): {e}")

    def on_press(self, event):
        """Check if a scatter point is clicked."""
        if event.inaxes != self.ax or event.button != 1 or self.scatter_artist is None:
            return

        # Safety check: ensure artist is still valid
        if not self.scatter_artist.axes:
            logging.warning("Artist no longer has axes, drag disabled")
            return

        contains, info = self.scatter_artist.contains(event)

        if contains and DraggablePoints.lock is None:
            index_in_scatter_data = info['ind'][0]

            self.selected_index = index_in_scatter_data

            x_data = self.scatter_artist.get_offsets()[self.selected_index, 0]
            y_data = self.scatter_artist.get_offsets()[self.selected_index, 1]

            self.offset = (x_data - event.xdata, y_data - event.ydata)

            DraggablePoints.lock = self

            # Change point color to yellow to show it's selected
            colors = self.scatter_artist.get_facecolors()
            # colors[self.selected_index] = (1, 1, 0, 1)  # Yellow
            self.scatter_artist.set_facecolors(colors)
            self.canvas.draw_idle()
            logging.debug(f"Drag started on point index: {self.selected_index}")

    def on_move(self, event):
        """Update the position of the selected point while dragging."""
        if DraggablePoints.lock is not self or event.inaxes != self.ax or self.selected_index is None:
            return

        # Calculate new point position
        new_x = event.xdata + self.offset[0]
        new_y = event.ydata + self.offset[1]

        # --- CRITICAL LOGIC: Update underlying data ---
        # Determine which DataFrame and Line to update
        if self.is_main_profile_data == 'survey':  # For Survey Data (Old Logic)
            df = self.data_h.profile_data
            line_label = 'Profile Data Line'
        elif self.is_main_profile_data == 'master':  # <--- NEW: For Master Data
            df = self.data_h.current_master_profiles
            line_label = 'Master Profile'
        else:  # For Added Points (Red Points)
            df = None  # Handle added points separately below

        if df is not None:
            # Update the DataFrame by index location (iloc)
            df.iloc[self.selected_index, df.columns.get_loc('chainage')] = new_x
            df.iloc[self.selected_index, df.columns.get_loc('elevation')] = new_y  # Update 'elevation'

            # CRITICAL: If Master Profile, update the original 'elevation_od' column too,
            # if 'elevation' was created from it
            if self.is_main_profile_data == 'master' and 'elevation_od' in df.columns:
                df.iloc[self.selected_index, df.columns.get_loc('elevation_od')] = new_y

            # Update the Line2D object
            for line in self.ax.lines:
                if line.get_label() == line_label:
                    line.set_xdata(df['chainage'])
                    line.set_ydata(df['elevation'])
                    break

        elif not self.is_main_profile_data:  # Handle Added Points (Red Points)
            # Update the temporary added points lists (Red Points)
            self.data_h.added_points_x[self.selected_index] = new_x
            self.data_h.added_points_y[self.selected_index] = new_y

        # Update the scatter artist's position
        offsets = self.scatter_artist.get_offsets()
        offsets[self.selected_index] = [new_x, new_y]
        self.scatter_artist.set_offsets(offsets)

        self.canvas.draw_idle()

    def on_release(self, event):
        """Finalize the drag operation."""
        if DraggablePoints.lock is not self:
            return

        # Reset point color
        colors = self.scatter_artist.get_facecolors()
        # Use the appropriate color depending on the target
        original_color = (0.678, 0.847, 0.902, 1) if self.is_main_profile_data else (1, 0, 0, 1)  # lightblue/red
        # colors[self.selected_index] = original_color
        self.scatter_artist.set_facecolors(colors)

        DraggablePoints.lock = None
        self.selected_index = None
        self.offset = (0, 0)
        self.canvas.draw_idle()
        logging.debug("Drag ended. Data updated.")


# --- PyQt GUI Application ---
class ProfileQCApp(QWidget):
    """The main PyQt GUI for the Profile QC Tool."""
    session_ended = pyqtSignal()

    def __init__(self, new_survey_topo_data, survey_unit,survey_type ,parent =None):
        super().__init__(parent)

        self.dialog = parent

        logging.info("Initializing ProfileQCApp GUI.")
        self.setWindowTitle(f"Profile QC Tool - {survey_unit}")
        self.data_handler = DataHandler(new_survey_topo_data, survey_unit)
        self.survey_type = survey_type

        if self.data_handler.has_survey_been_marked_as_failed():
            # Show warning
            QMessageBox.critical(
                self,
                "Survey Already Failed",
                "This survey has already been marked as Failed. The QC session will now exit."
            )
            logging.warning("Survey marked as Failed. Exiting QC session.")

            # Close properly
            if self.dialog:
                self.dialog.reject()  # reject() or accept(), depending on your logic
            else:
                self.close()
            return


        self.added_profile_lines = []
        self.scatter_artist = None  # For added red points
        self.survey_points_artist = None  # For main profile blue points
        self.draggable = None  # Placeholder for the DraggablePoints instance

        self.point_add_target = 'survey' # Tracks middle-click target for adding points

        self.temp_files_already_exist = False  # Tracks if temp files were present at startup

        self.init_ui()
        self.connect_signals()
        self.initial_load()

    def initial_load(self):
        """Loads and plots the very first profile (index 0) explicitly."""

        # 1. Reset index to 0 (just for safety)
        self.data_handler.current_index = 0





        self.temp_files_already_exist = self.data_handler.check_temp_files_exist()

        # 2. Load the data for index 0
        self.data_handler.load_current_profile()

        # 3. Draw the plot
        self.update_plot()
        logging.info("GUI loaded and plotted profile 0 successfully.")

        QTimer.singleShot(100, self.check_temp_files_prompt)

    def init_ui(self):
        # === 1. Main Window Layout ===

        container = QWidget()
        container.setObjectName("ProfileQCContainer")

        # Apply layout to container
        main_layout = QVBoxLayout(container)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(8)

        # === 2. Global Styles (QSS) ===
        # Set stylesheet on the container
        container.setStyleSheet("""
               #ProfileQCContainer QFrame#ControlFrame {
                   border: 1px solid #ccc;
                   border-radius: 6px;
                   padding: 8px;
                   background-color: #fafafa;
               }
               #ProfileQCContainer QPushButton {
                   padding: 6px 14px;
                   border-radius: 4px;
                   font-weight: 500;
                   border: 1px solid #bbb;
                   background-color: black;
               }
               #ProfileQCContainer QPushButton:hover {
                   background-color: #e0e0e0;
               }
               #ProfileQCContainer QPushButton#SaveButton {
                   background-color: #28a745;
                   color: white;
                   border: none;
               }
               #ProfileQCContainer QPushButton#SaveButton:hover {
                   background-color: #218838;
               }
               #ProfileQCContainer QPushButton#DragButton, #ProfileQCContainer QPushButton#AddTargetButton {
                   background-color: #007bff;
                   color: white;
                   border: none;
               }
               #ProfileQCContainer QPushButton#DragButton:hover, #ProfileQCContainer QPushButton#AddTargetButton:hover {
                   background-color: #0069d9;
               }
               #ProfileQCContainer QPushButton:checked {
                   background-color: #dc3545;
                   color: white;
               }
           """)

        # Now set the container as the layout for self
        wrapper_layout = QVBoxLayout(self)
        wrapper_layout.setContentsMargins(0, 0, 0, 0)
        wrapper_layout.addWidget(container)

        # === 3. Matplotlib Canvas & Toolbar ===
        self.canvas_widget = MplCanvas(self)
        self.ax = self.canvas_widget.axes
        self.toolbar = NavigationToolbar(self.canvas_widget, self)

        main_layout.addWidget(self.toolbar)
        main_layout.addWidget(self.canvas_widget, stretch=5)
        # === 4. Controls Section ===
        controls_frame = QFrame()
        controls_frame.setObjectName("ControlFrame")
        controls_layout = QHBoxLayout(controls_frame)
        controls_layout.setContentsMargins(10, 5, 10, 5)
        controls_layout.setSpacing(15)

        # --- Warning Bar (Top Center) ---
        self.warning_frame = QFrame()
        self.warning_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        warning_layout = QHBoxLayout(self.warning_frame)
        warning_layout.setContentsMargins(10, 0, 10, 0)

        self.warning_label = QLabel("⚠️ No warnings")
        self.warning_label.setAlignment(Qt.AlignCenter)
        self.warning_label.setStyleSheet("font-weight: bold; color: white;")
        warning_layout.addWidget(self.warning_label)

        main_layout.insertWidget(0, self.warning_frame)

        def add_group(*widgets):
            """Helper to create neatly grouped button sets."""
            frame = QFrame()
            layout = QHBoxLayout(frame)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(5)
            for w in widgets:
                layout.addWidget(w)
            controls_layout.addWidget(frame)
            controls_layout.addStretch(1)

        # --- Navigation ---
        self.btn_prev = self._create_button("⬅️ Prev Profile", self.prev_profile)
        self.btn_next = self._create_button("Next Profile ➡️ ", self.next_profile)
        add_group(self.btn_prev, self.btn_next)

        # --- Editing Tools ---
        self.btn_add_target = self._create_button("Add Points Mode: Survey", self.toggle_add_target)
        self.btn_add_target.setCheckable(True)
        self.btn_add_target.setObjectName("AddTargetButton")

        self.btn_drag = self._create_button("✏️ Drag Mode (D)", self.toggle_drag_mode)
        self.btn_drag.setCheckable(True)
        self.btn_drag.setObjectName("DragButton")
        add_group(self.btn_add_target, self.btn_drag)

        # --- Data Actions ---
        self.btn_save = self._create_button("💾 Apply Changes (Enter)", self.save_and_update)
        self.btn_save.setObjectName("SaveButton")

        self.btn_delete = self._create_button("❌ Delete Changes (Del)", self.delete_and_update)


        self.btn_flag = self._create_button("🚩 Flag Profile (I)", self.flag_profile)
        add_group(self.btn_save, self.btn_delete, self.btn_flag)

        # --- Session Controls ---
        self.btn_add_more = self._create_button("➕ Add DB Profiles (M)", self.add_more_profiles)
        self.btn_remove_more = self._create_button("➖ Remove DB Profiles (R)", self.remove_added_profiles)
        self.btn_end = self._create_button("🛑 End Session (End)", self.end_session)
        add_group(self.btn_add_more, self.btn_remove_more, self.btn_end)

        main_layout.addWidget(controls_frame)

        # === 5. Status Label ===
        self.status_label = QLabel(f"Loaded Profile: {self.data_handler.profile}. Added Points: 0")
        self.status_label.setStyleSheet("font-weight: 500; color: #333; padding: 5px 0;")
        main_layout.addWidget(self.status_label)

        self.btn_finish_push = self._create_button("✅ Finish and Push", self.finish_and_push)
        self.btn_finish_push.setObjectName("FinishPushButton")
        self.btn_finish_push.hide()  # hide by default
        add_group(self.btn_finish_push)

        self.btn_undo = self._create_button("❌ Undo Database Change", self.undo_push)
        self.btn_undo.setObjectName("UndoDatabasePush")
        add_group(self.btn_undo)
        self.btn_finish_push.show()




        # === 6. Window Settings ===
        self.setMinimumSize(1000, 700)
        self.showMaximized()

    def check_temp_files_prompt(self):
        """Prompt user about existing temporary files after window loads."""
        if getattr(self, "temp_files_already_exist", False):
            reply = QMessageBox.question(
                self,
                "Temporary Files Detected",
                "Temporary files from a previous session were found.\n\n"
                "Would you like to clear them before continuing?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes
            )

            if reply == QMessageBox.Yes:
                try:
                    self.data_handler.clean_up_temp_files()
                    QMessageBox.information(self, "Cleanup Complete", "Temporary files have been cleared.")
                except Exception as e:
                    QMessageBox.warning(self, "Error", f"Failed to clear temporary files:\n{e}")
                    quit()

    def _create_button(self, text, handler):
        btn = QPushButton(text)
        btn.clicked.connect(handler)
        return btn

    def update_warning_bar(self):

        try:

            if self.data_handler.flagged_profiles and self.data_handler.profile in self.data_handler.flagged_reasons.keys():
                self.warning_frame.setStyleSheet("""
                                                        background-color:red;
                                                        border: 2px solid #8C240F;
                                                        border-radius: 6px;
                                                        padding: 6px;
                                                    """)
                self.warning_label.setStyleSheet("font-weight: bold; color: black;")
                flag_issue = self.data_handler.flagged_reasons.get(self.data_handler.profile)

                message = f"Flagged Profile: {flag_issue}"
                self.warning_label.setText(f"⚠️ {message}")

                return


            issues = self.data_handler.profile_issues.get("flags")

            if issues:

                if "Survey chainage values are not strictly increasing" in issues or "Survey does not cross master profile anywhere!" in issues or "Survey does not reach master profile landward limit" in issues:
                    # Red warning
                    self.warning_frame.setStyleSheet("""
                                        background-color:red;
                                        border: 2px solid #8C240F;
                                        border-radius: 6px;
                                        padding: 6px;
                                    """)
                    self.warning_label.setStyleSheet("font-weight: bold; color: black;")
                    message = " | ".join(issues)
                    self.warning_label.setText(f"⚠️ {message}")
                else:
                    # Yellow warning
                    self.warning_frame.setStyleSheet("""
                        background-color: #ffc107;
                        border: 2px solid #ffa500;
                        border-radius: 6px;
                        padding: 6px;
                    """)
                    self.warning_label.setStyleSheet("font-weight: bold; color: black;")
                    message = " | ".join(issues)
                    self.warning_label.setText(f"⚠️ {message}")

            else:
                # Green no issues
                self.warning_frame.setStyleSheet("""
                    background-color: #28a745;
                    border: 2px solid #218838;
                    border-radius: 6px;
                    padding: 6px;
                """)
                self.warning_label.setStyleSheet("font-weight: bold; color: white;")
                self.warning_label.setText("✅ No warnings")
        except AttributeError:
            # Default state
            self.warning_frame.setStyleSheet("""
                background-color: #28a745;
                border: 2px solid #218838;
                border-radius: 6px;
                padding: 6px;""")

    def update_finish_button_visibility(self):
        """Show 'Finish and Push' only when certain conditions are met. We
           need all profiles to have CPA, Profile, and MP tmp files created."""

        # if any profiles have been flagged, then we do show the button, but the button action will prevent pushing
        # and instead set the depending on the issue rejected for the survey in the database

        if self.data_handler.flagged_profiles:
            self.btn_finish_push.setVisible(True)
            return


        check_all_cpa_created = False
        check_all_profiles_created = False
        check_all_mp_created = False

        temp_dir = tempfile.gettempdir()
        date_string = self.data_handler.date.strftime("%Y%m%d")
        for profile in self.data_handler.unique_profiles['reg_id']:

            #1) Check all CPA files created for all profiles
            cpa_output_path = os.path.join(temp_dir, 'Calculated_CPA_Values',
                                           f"{self.data_handler.survey_unit}_{profile}{date_string}.pkl")
            if not os.path.exists(cpa_output_path):
                check_all_cpa_created = False
                break
            check_all_cpa_created = True

            # 2) Check all Profile files created for all profiles
            profile_output_path = os.path.join(temp_dir, 'New_Profile_Data',
                                           f"{self.data_handler.survey_unit}_{profile}{date_string}.pkl")
            if not os.path.exists(profile_output_path):
                check_all_profiles_created = False
                break
            check_all_profiles_created = True

            # 3) Check all MP files created for all profiles
            mp_output_path = os.path.join(temp_dir, 'New_MP_Data',
                                               f"MASTER_{self.data_handler.survey_unit}_{profile}_{date_string}.pkl")
            if not os.path.exists(mp_output_path):
                check_all_mp_created = False
                break
            check_all_mp_created = True

        condition_met = (
            check_all_cpa_created and check_all_profiles_created and check_all_mp_created )

        # check for any cirtical issues for all profiles
        if condition_met:

            # list all files in the New_Profile_Data folder
            profile_files = os.listdir(os.path.join(temp_dir, 'New_Profile_Data'))
            mp_files = os.listdir(os.path.join(temp_dir, 'New_MP_Data'))

            profile_paths = []
            mp_paths = []

            for pf in profile_files:
                profile_path = os.path.join(temp_dir, 'New_Profile_Data', pf)
                profile_paths.append(profile_path)
            for mf in mp_files:
                mp_path = os.path.join(temp_dir, 'New_MP_Data', mf)
                mp_paths.append(mp_path)

            mp_profile_paths = list(zip(profile_paths, mp_paths))
            try:

                for profile_path, mp_path in mp_profile_paths:
                    profile_df = pd.read_pickle(profile_path)
                    mp_df = pd.read_pickle(mp_path)
                    issue_dict = qc_profile(mp_df, profile_df)
                    critical_issues = {
                        "Survey chainage values are not strictly increasing",
                        "Survey does not cross master profile anywhere!",
                        "Survey does not reach master profile landward limit",
                        "Profile does not reach MLW elevation"
                    }

                    if any(flag in critical_issues for flag in issue_dict.get("flags", [])):
                        condition_met = False
                        break

            except Exception as e:
                logging.error(f"Error during final QC check: {e}")
                condition_met = False


        self.btn_finish_push.setVisible(condition_met)

    def end_session(self):
        self.data_handler.end_session()
        if self.dialog:
            self.dialog.accept()

    def finish_and_push(self):
        """Finalize and push all profiles to the database. Create Sands Ready Files etc."""

        has_data_already_been_pushed = self.data_handler.check_if_database_push_completed()
        if has_data_already_been_pushed:
            QMessageBox.warning(
                None,
                "Data Already Pushed",
                "⚠️ It appears that this survey's data has already been pushed to the database.\n\n"
                "Pushing again may result in duplicate entries or data conflicts.\n\n"
                "Please use the undo database push button first.",
                QMessageBox.Ok
            )
            logging.info("Push aborted: Data has already been pushed to the database.")
            return

        if self.data_handler.flagged_profiles:
          confirm = QMessageBox.warning(self, "Flagged Profiles",
                                "One or more profiles have been flagged. Pushing will set pass the selected fail reason to Admin for review.\n\n",
                                        QMessageBox.Yes | QMessageBox.No)
        else:
            confirm = QMessageBox.question(
                self,
                "Confirm Push",
                "Are you sure you want to finalize and push all profiles?",
                QMessageBox.Yes | QMessageBox.No,
            )

        if confirm == QMessageBox.Yes:
            try:
                if self.data_handler.flagged_profiles:
                    self.data_handler.mark_survey_as_rejected()
                else:



                    self.data_handler.end_session_and_push()
                    #self.data_handler.prepare_sands_ready_files()

            except Exception as e:
                logging.error(f"Error pushing data files: {e}")
                QMessageBox.warning(self, "Error",
                                    f"An error occurred while creating Sands Ready files:\n{e}")


                return

            self.update_plot()
            self.delete_and_update()


            self.end_session()


    def undo_push(self):
        """Undo the last database push by restoring from history."""
        confirm = QMessageBox.question(
            self,
            "Confirm Undo",
            "Are you sure you want to undo the last database push? This will restore all previous edits saved.",
            QMessageBox.Yes | QMessageBox.No,
        )
        if confirm == QMessageBox.Yes:
            self.data_handler.undo_last_push()

            self.update_plot()
            self.delete_and_update()
            QMessageBox.information(self, "Done", "The last database push has been undone.")

    def connect_signals(self):
        # Connect Matplotlib events to PyQt methods
        self.canvas_widget.mpl_connect('button_press_event', self.on_mpl_click)

    def toggle_add_target(self):
        """Toggles the target for middle-click point addition between Survey and Master."""
        if self.point_add_target == 'survey':
            if self.data_handler.current_master_profiles is None or self.data_handler.current_master_profiles.empty:
                QMessageBox.warning(self, "No Master Data", "Master profile data is not loaded or is empty.")
                self.btn_add_target.setChecked(False)
                return

            self.point_add_target = 'master'
            self.btn_add_target.setText("Add Point Mode: Master")
            logging.info("Point addition target set to Master Profile.")
        else:
            self.point_add_target = 'survey'
            self.btn_add_target.setText("Add Point Mode: Survey")
            logging.info("Point addition target set to Survey Profile.")

        self.status_label.setText(f"Click middle mouse button to add points to {self.point_add_target.capitalize()}.")

    def update_plot(self):
        """Redraws the plot based on the current data state."""
        data_h = self.data_handler
        if self.draggable:
            logging.info("Forcing disconnection of DraggablePoints before plot update.")
            self.draggable.disconnect()
            self.draggable = None  # Explicitly set to None
            self.btn_drag.setChecked(False)  # Reset button state
            # Ensure the lock is globally cleared if it wasn't on the release event
            DraggablePoints.lock = None

        self.ax.clear()
        logging.debug(f"Plotting Profile: {data_h.profile} (Index: {data_h.current_index})")

        # Reset artists before plotting
        self.scatter_artist = None
        self.survey_points_artist = None
        self.master_points_artist = None
        self.added_profile_line_artist = None

        if data_h.profile_data is not None and not data_h.profile_data.empty:

            try:
                over_spacing_index = find_over_spacing(data_h.profile_data)
            except Exception as e:
                logging.error(f"Error finding over spacing: {e}")
                over_spacing_index = []



            # 1a. Plot the main profile LINE
            self.ax.plot(
                data_h.profile_data['chainage'],
                data_h.profile_data['elevation'],
                label='Profile Data Line',
                color='blue',
                zorder=2
            )

            if over_spacing_index:

                # Build a color list for each point based on index
                colors = [
                    '#e312c7' if idx in over_spacing_index else 'lightblue'
                    for idx in data_h.profile_data.index
                ]

                # 1b. Plot the main profile POINTS (Used for dragging)
                self.survey_points_artist = self.ax.scatter(
                    data_h.profile_data['chainage'],
                    data_h.profile_data['elevation'],
                    label='Profile Data Points',
                    color=colors,
                    picker=5,
                    zorder=3
                )
            else:
                # 1b. Plot the main profile POINTS (Used for dragging)
                self.survey_points_artist = self.ax.scatter(
                    data_h.profile_data['chainage'],
                    data_h.profile_data['elevation'],
                    label='Profile Data Points',
                    color='lightblue',
                    picker=5,
                    zorder=3
                )

            if 'fc' in data_h.profile_data.columns:
                for x, y, fc_val in zip(data_h.profile_data['chainage'],
                                        data_h.profile_data['elevation'],
                                        data_h.profile_data['fc']):
                    # Offset slightly in y so labels don’t overlap the points
                    self.ax.text(x, y + 0.05, str(fc_val), fontsize=8, ha='center', va='bottom', color='darkblue',
                                 zorder=4)

            logging.debug("Plotted survey profile line and draggable points.")

            # 2. Plot the master profile
            if data_h.current_master_profiles is not None and not data_h.current_master_profiles.empty:
                master_data = data_h.current_master_profiles.copy()
                #master_data = master_data.sort_values(by=['chainage']).sort_index()
                print(master_data)

                if 'elevation_od' in master_data.columns and 'elevation' not in master_data.columns:
                    master_data['elevation'] = pd.to_numeric(master_data['elevation_od'], errors='coerce')

                # 2a. Plot the Master Profile line (unchanged)
                self.ax.plot(
                    master_data['chainage'],
                    master_data['elevation'],
                    label='Master Profile',
                    color='red',
                )

                # 2b. Plot Master Profile POINTS (New draggable artist)
                self.master_points_artist = self.ax.scatter(
                    master_data['chainage'],
                    master_data['elevation'],
                    label='Master Profile Points',
                    color='gray',  # Use a distinct color for MP points
                    picker=5,
                    zorder=3
                )
                logging.debug("Plotted master profile line and draggable points.")
            else:
                logging.debug("Master profile data is empty or connection failed, skipping plot.")

            # 3. Plot ADDED HISTORICAL PROFILES (New Section)
            if data_h.show_historical_profiles and data_h.historical_profiles:

                # Re-determine closest dates to apply colors/labels correctly
                all_dates = list(data_h.historical_profiles.keys())
                date_obj = pd.to_datetime(data_h.date)
                sorted_by_distance = sorted(all_dates, key=lambda x: abs(x - date_obj))
                closest_date = sorted_by_distance[0]
                second_closest_date = sorted_by_distance[1] if len(sorted_by_distance) > 1 else None

                # Iterate and plot all historical data stored in the DataHandler
                for date, filter_data in data_h.historical_profiles.items():

                    # Determine color and label based on date (same logic as before)
                    color, alpha, label = ('gray', 0.4, None)
                    if date == closest_date:
                        color, label = ('red', f"Closest Date: {date.date()}")
                        alpha = 0.6
                    elif date == second_closest_date:
                        color, label = ('pink', f"Second Closest: {date.date()}")
                        alpha = 0.6

                    # Plot the line (Assigning to a variable is optional here as we don't need the artist later)
                    self.ax.plot(
                        filter_data['chainage'],
                        filter_data['elevation'],
                        color=color,
                        alpha=alpha,
                        label=label,
                        zorder=1  # Ensure these historical lines are drawn behind the main line (zorder=2)
                    )

                logging.debug("Historical profiles re-plotted.")

            # 3. Plot temporary added points
            if data_h.added_points_x:
                self.scatter_artist = self.ax.scatter(
                    data_h.added_points_x, data_h.added_points_y, color='red', label='Added Points', zorder=5
                )
                logging.debug(f"Plotted {len(data_h.added_points_x)} added points.")
            else:
                self.scatter_artist = None  # CRITICAL: MUST be set to None if no points

            # 4. Check for 'M' profiles and redraw them if they were active
            if self.added_profile_lines:
                self.add_more_profiles(was_active=True)

        # 5. Labels and legend
        self.ax.set_xlabel('Chainage')
        self.ax.set_ylabel('Elevation')
        self.ax.set_title(
            f"Profile: {data_h.profile} - Index: {data_h.current_index}/{len(data_h.unique_profiles) - 1}")
        self.ax.legend()
        self.canvas_widget.draw()
        self.status_label.setText(f"Loaded Profile: {data_h.profile}. Added Points: {len(data_h.added_points_x)}")
        logging.debug("Plotting complete and canvas drawn.")
        self.update_warning_bar()
        # Check if 'Finish and Push' button should be visible
        self.update_finish_button_visibility()

    # --- Navigation and Action Handlers (Unchanged) ---
    def next_profile(self):
        logging.info("User action: Next Profile (->)")
        self.remove_added_profiles()
        if self.draggable:  # Block navigation if dragging is active
            logging.warning("Preventing navigation: Drag Mode is active.")
            QMessageBox.warning(self, "Drag Mode Active", "Disable Drag Mode before navigating.")
            return

        if self.data_handler.current_index < len(self.data_handler.unique_profiles) - 1:
            if self.data_handler.added_points_x:
                logging.warning("Preventing navigation: Unsaved changes exist.")
                QMessageBox.warning(self, "Unsaved Changes",
                                    "Please press 'Apply Changes' or 'Delete Changes' before moving to the next profile.")
                return

            self.data_handler.log_index()
            self.data_handler.current_index += 1
            self.data_handler.load_current_profile()
            self.added_profile_lines.clear()
            self.update_plot()
        else:
            logging.warning("Navigation stopped: Reached last profile.")
            self.status_label.setText("Reached last profile.")

        # Check if 'Finish and Push' button should be visible
        self.update_finish_button_visibility()

    def prev_profile(self):
        logging.info("User action: Previous Profile (<-)")
        self.remove_added_profiles()
        if self.draggable:  # Block navigation if dragging is active
            logging.warning("Preventing navigation: Drag Mode is active.")
            QMessageBox.warning(self, "Drag Mode Active", "Disable Drag Mode before navigating.")
            return

        if self.data_handler.current_index > 0:
            if self.data_handler.added_points_x:
                logging.warning("Preventing navigation: Unsaved changes exist.")
                QMessageBox.warning(self, "Unsaved Changes",
                                    "Please press 'Apply Changes' or 'Delete Changes' before moving back.")
                return

            self.data_handler.log_index()
            self.data_handler.current_index -= 1
            self.data_handler.load_current_profile()
            self.added_profile_lines.clear()
            self.update_plot()
        else:
            logging.warning("Navigation stopped: At the first profile.")
            self.status_label.setText("At the first profile.")

        # Check if 'Finish and Push' button should be visible
        self.update_finish_button_visibility()

    def save_and_update(self):
        logging.info("User action: Apply Changes (Enter)")
        try:

            self.data_handler.save_changes()
        except Exception as e:
            logging.error(f"Error saving changes: {e}")
            QMessageBox.warning(self, "Error", f"An error occurred while saving changes:\n{e}")
            return

        self.update_plot()

        # Check if 'Finish and Push' button should be visible
        self.update_finish_button_visibility()

    def delete_and_update(self):
        logging.info("User action: Delete Changes (Del)")
        self.data_handler.delete_changes()
        self.update_plot()
        # Check if 'Finish and Push' button should be visible
        self.update_finish_button_visibility()


    def flag_profile(self):
        logging.warning(f"User action: Flag Profile (I) for {self.data_handler.profile} {self.survey_type}")

        fields_that_use_enum = [
            "checks_pl_point_spacing",
            "checks_pl_seaward_limit",
            "checks_pl_profile_start_position",

        ]

        issue_map = {"Excessive Over Spacing":["checks_pl_point_spacing", "checks_pl_point_spacing_c"],
                     "Survey Does Not Reach Master Profile Landward Limit":["checks_pl_profile_start_position","checks_pl_profile_start_position_c"],
                     "Survey does Not Reach Seaward Limit":["checks_pl_seaward_limit","checks_pl_seaward_limit"],
                    }


        # Define standardized reasons
        reasons = [
            "Excessive Over Spacing",
            "Survey Does Not Reach Master Profile Landward Limit",
            "Survey does Not Reach Seaward Limit",

        ]


        # Ask user to select reason
        reason, ok = QInputDialog.getItem(
            self,
            "Flag Profile",
            "Select the issue with this profile:",
            reasons,
            0,  # Default selection index
            False  # Editable = False (no custom typing)
        )

        if ok and reason:
            logging.info(f"Profile flagged for reason: {reason}")

            # Store the profile flagged and the reason
            self.data_handler.flagged_profiles = True
            self.data_handler.flagged_reasons.update({self.data_handler.profile: reason})

            QMessageBox.information(
                self,
                "Profile Flagged",
                f"Profile '{self.data_handler.profile}' flagged for:\n{reason}"
            )
            self.update_warning_bar()

            # You could also trigger your backend flagging here:
            # self.database_handler.flag_profile(self.data_handler.profile, reason)

        elif ok:
            QMessageBox.warning(
                self,
                "No Selection",
                "You must select a reason to flag this profile."
            )



        else:
            logging.info("User cancelled flagging.")




        QMessageBox.information(self, "Flag Profile", f"Profile {self.data_handler.profile} Flagged for Review.")

    # --- Mouse Event Handler (Unchanged) ---
    def on_mpl_click(self, event):
        """Handles mouse clicks on the Matplotlib canvas."""
        if self.draggable:  # Block adding points if dragging is active
            logging.debug("Ignoring middle click: Drag Mode is active.")
            return

        if event.button == 2 and event.inaxes:
            x_clicked = event.xdata
            y_clicked = event.ydata

            target = self.point_add_target  # Get the current target

            if target == 'survey':
                # Existing logic: add to temporary survey points
                self.data_handler.added_points_x.append(x_clicked)
                self.data_handler.added_points_y.append(y_clicked)
                logging.debug(f"Survey point added at ({x_clicked:.2f}, {y_clicked:.2f}).")

            elif target == 'master':
                # NEW LOGIC: Add directly to the in-memory Master DataFrame
                df = self.data_handler.current_master_profiles
                if df is not None:

                    # Create a new row of data (using None for potentially missing columns)
                    new_row = df.iloc[0].copy()

                    # Update the critical columns
                    new_row['chainage'] = x_clicked
                    new_row['elevation'] = y_clicked
                    if 'elevation_od' in new_row:
                        new_row['elevation_od'] = y_clicked

                    # Append the new row to the DataFrame
                    # Using pd.concat is cleaner than append/iloc manipulation for adding rows
                    self.data_handler.current_master_profiles = pd.concat([
                        df, new_row.to_frame().T
                    ], ignore_index=True)

                    # Sort the Master Profile by chainage after adding
                    self.data_handler.current_master_profiles = self.data_handler.current_master_profiles.sort_values(
                        'chainage')

                    logging.debug(f"Master point added at ({x_clicked:.2f}, {y_clicked:.2f}).")
                else:
                    logging.warning("Cannot add Master point: Master profile data is None.")
                    QMessageBox.warning(self, "Error", "Cannot add point; Master Profile data is not initialized.")

            self.update_plot()

    # --- Drag Mode Toggle ---
    def toggle_drag_mode(self):
        """Enables or disables point dragging, targeting the main profile points."""

        # Toggle off logic
        if self.draggable:
            self.draggable.disconnect()
            self.draggable = None
            self.btn_drag.setChecked(False)
            self.status_label.setText("Click middle mouse button to add points.")
            # CRITICAL: Reset the class lock here to ensure a clean state
            DraggablePoints.lock = None
            logging.info("Drag mode disabled successfully")
            return

        targets = []
        if self.survey_points_artist is not None and not self.data_handler.profile_data.empty:
            targets.append('Survey (New Data)')
        if self.master_points_artist is not None and not self.data_handler.current_master_profiles.empty:
            targets.append('Master (DB Data)')

        if not targets:
            QMessageBox.warning(self, "No Data", "No profile points loaded to drag.")
            self.btn_drag.setChecked(False)
            return

        # Get user choice using a standard QMessageBox as a simple prompt
        msg = QMessageBox(self)
        msg.setWindowTitle("Select Drag Target")
        msg.setText("Which profile would you like to edit?")

        # Use buttons based on available targets
        btn_survey = None
        btn_master = None

        if 'Survey (New Data)' in targets:
            btn_survey = msg.addButton("Survey", QMessageBox.YesRole)
        if 'Master (DB Data)' in targets:
            btn_master = msg.addButton("Master", QMessageBox.NoRole)

        msg.addButton("Cancel", QMessageBox.RejectRole)

        msg.exec_()

        # Determine selection
        target_artist = None
        drag_target = None

        clicked_button = msg.clickedButton()

        if clicked_button == btn_survey and btn_survey:
            target_artist = self.survey_points_artist
            drag_target = 'survey'
        elif clicked_button == btn_master and btn_master:
            target_artist = self.master_points_artist
            drag_target = 'master'
        else:  # Cancel or no selection
            self.btn_drag.setChecked(False)
            return

        # Disable the Matplotlib Pan/Zoom toolbar actions to avoid conflict
        for action in self.toolbar.actions():
            if action.isCheckable():
                action.setChecked(False)

        # Instantiate DRAG HANDLER
        # NOTE: drag_target is now a string: 'survey' or 'master'
        self.draggable = DraggablePoints(self, target_artist, drag_target=drag_target)
        self.btn_drag.setChecked(True)
        self.status_label.setText(
            f"DRAG MODE ACTIVE: Editing {drag_target.upper()} Profile. Press 'D' or button to exit.")

    # --- Key Press Event (Updated) ---
    def keyPressEvent(self, event):
        """Handles global key presses for navigation and actions."""
        key = event.key()

        if key == Qt.Key_D:
            self.btn_drag.toggle()
            self.toggle_drag_mode()

        elif self.draggable:
            # Prevent other actions/navigation when dragging is active
            return

        elif key == Qt.Key_Right:
            self.next_profile()
        elif key == Qt.Key_Left:
            self.prev_profile()
        elif key == Qt.Key_Return or key == Qt.Key_Enter:
            self.save_and_update()
        elif key == Qt.Key_Delete:
            self.delete_and_update()
        elif key == Qt.Key_M:
            self.add_more_profiles()
        elif key == Qt.Key_R:
            self.remove_added_profiles()
        elif key == Qt.Key_I:
            self.flag_profile()
        elif key == Qt.Key_End:
            self.data_handler.end_session()
        else:
            super().keyPressEvent(event)

    # --- Auxiliary Plotting Methods (Unchanged) ---

    def add_more_profiles(self, was_active=False):
        """Fetches historical profile data from DB and sets the display state."""

        if not was_active:
            logging.info("User action: Add DB Profiles (M).")
            # Toggle state flag ON
            self.data_handler.show_historical_profiles = True

        # If already active, we assume the data is present and skip the DB call
        if self.data_handler.historical_profiles and was_active:
            logging.debug("Historical data already loaded. Forcing plot update.")
            # Trigger the plot to redraw the existing data
            self.update_plot()
            return

        # --- Database Connection and Query (UNCHANGED) ---
        conn = establish_connection()
        if not conn:
            # ... (error handling and return) ...
            return

        current_profile = self.data_handler.profile
        db_topo_query = (
            f"SELECT * FROM topo_qc.topo_data WHERE profile = '{current_profile}'"
        )
        db_topo_data = get_data(db_topo_query, conn)
        conn.close()

        if db_topo_data.empty:
            # Toggle state flag OFF if no data found
            self.data_handler.show_historical_profiles = False
            self.status_label.setText("No historical profile data available.")
            logging.warning(f"No historical data found for profile {current_profile}")
            return

        # --- Data Processing and Storage ---
        self.data_handler.historical_profiles.clear()  # Clear existing data
        db_topo_data['date'] = pd.to_datetime(db_topo_data['date'])

        # Determine closest dates (UNCHANGED)
        unique_dates = sorted(db_topo_data['date'].unique(), reverse=True)
        date_obj = pd.to_datetime(self.data_handler.date)
        sorted_by_distance = sorted(unique_dates, key=lambda x: abs(x - date_obj))
        closest_date = sorted_by_distance[0]
        second_closest_date = sorted_by_distance[1] if len(sorted_by_distance) > 1 else None

        # Store filtered and processed data frames in the data handler
        for date in unique_dates:
            filter_data = db_topo_data.loc[db_topo_data['date'] == date].copy()

            # --- CRITICAL: Ensure Data is Numeric and Cleaned ---
            filter_data['chainage'] = pd.to_numeric(filter_data['chainage'], errors='coerce')
            if 'elevation_od' in filter_data.columns and 'elevation' not in filter_data.columns:
                filter_data['elevation'] = pd.to_numeric(filter_data['elevation_od'], errors='coerce')
            elif 'elevation' in filter_data.columns:
                filter_data['elevation'] = pd.to_numeric(filter_data['elevation'], errors='coerce')

            filter_data = filter_data.drop_duplicates(subset=['chainage', 'elevation']).sort_values(by='chainage')

            # Store the processed DataFrame
            self.data_handler.historical_profiles[date] = filter_data

        # --- Redraw the plot to show the new lines ---
        self.update_plot()
        logging.info(f"Historical profiles fetched and stored for {current_profile}.")

    def remove_added_profiles(self):
        """Removes all temporary historical profile lines."""
        logging.info("User action: Remove DB Profiles (R).")
        if not self.data_handler.historical_profiles:
            logging.debug("No added profiles to remove.")
            return

        self.data_handler.historical_profiles.clear()
        self.update_plot()
        logging.info("Removed historical profiles.")


#if __name__ == '__main__':
#    import sys
#    import os
#    from PyQt5.QtWidgets import QApplication, QMainWindow, QMessageBox
#    import logging
#
#    survey_path = r"C:\Users\darle\Desktop\Batcher_Test\Batch\6d6D2-13_20230222tp.txt"
#    survey_unit = '6d6D2-13'
#
#    logging.basicConfig(level=logging.INFO)
#    logging.info("Application starting.")
#
#    app = QApplication(sys.argv)
#
#    if not os.path.exists(survey_path):
#        logging.critical(f"Input file not found: {survey_path}")
#        QMessageBox.critical(None, "Fatal Error", f"Input file not found: {survey_path}")
#        sys.exit(1)
#
#    try:
#        main_window = QMainWindow()
#        qc_widget = ProfileQCApp(new_survey_topo_data=survey_path, survey_unit=survey_unit)
#        main_window.setCentralWidget(qc_widget)
#        main_window.show()
#        sys.exit(app.exec_())
#    except Exception as e:
#        logging.critical("Unhandled exception in main application loop.", exc_info=True)
#        QMessageBox.critical(None, "Application Error",
#                             f"An unhandled error occurred: {e}. Check logs for details.")
#        sys.exit(1)
#


# --- Execution Block ---
#if __name__ == '__main__':
#
#    # NOTE: This path MUST be valid for the script to load data
#    # Change this MOCK path to your actual data file path
#    #survey_path = r"X:\Data\Survey_Topo\Phase4\TSW02\6d\6d6D2-4_ParSands\6d6D2-4_20250115tip\Batch\6d6D2-4_20250115tip.txt"
#    survey_path =r"C:\Users\darle\Desktop\Batcher_Test\Batch\6d6D2-13_20230222tp.txt"
#
#    survey_unit = '6d6D2-13'  # Example unit name
#
#    logging.info("Application starting.")
#
#    app = QApplication(sys.argv)
#
#    if not os.path.exists(survey_path):
#        logging.critical(f"Input file not found: {survey_path}")
#        QMessageBox.critical(None, "Fatal Error", f"Input file not found: {survey_path}")
#        sys.exit(1)
#
#    try:
#        main_window = ProfileQCApp(new_survey_topo_data=survey_path, survey_unit=survey_unit)
#        sys.exit(app.exec_())
#    except Exception as e:
#        logging.critical("Unhandled exception in main application loop.", exc_info=True)
#        QMessageBox.critical(None, "Application Error",
#                             f"An unhandled error occurred: {e}. Check {LOG_FILE} for details.")
#        sys.exit(1)
#
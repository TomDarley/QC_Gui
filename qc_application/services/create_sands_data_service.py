import logging
from datetime import time, datetime
from pathlib import Path

from pandas.core.base import PandasObject
from sqlalchemy import text, bindparam
from qc_application.utils.database_connection import establish_connection
import pandas as pd
import os



class CreateSandsDataService:
    def __init__(self, survey_unit, date):
        self.survey_unit = survey_unit
        self.date = date

    def execute(self):
        # Step 1: Validate the input data
        if not self.survey_unit or not self.date:
            logging.error(f"Invalid input data: survey_unit={self.survey_unit}, date={self.date}")
            return False
        # Step 2: Fetch topo data for the given survey_unit and date
        selected_topo_data = self.get_topo_data_ready_for_conversion(self.survey_unit, self.date)

        #Step 3: Check if topo data is available
        if  selected_topo_data.empty:
            logging.warning(f"No topo data found for survey_unit={self.survey_unit}, date={self.date}")
            return False

        # Step 4: Fetch master profile data based on the topo data
        selected_master_profile_data = self.get_master_profile_data_ready_for_sands(
            self.survey_unit,
            self.date,
            selected_topo_data
        )

        # Sep 5: Check if master profile data is available
        if selected_master_profile_data.empty:
            logging.warning(f"No master profile data found for survey_unit={self.survey_unit}, date={self.date}")
            return False

        formatted_topo_data, topo_outfile = self.format_topo_data_for_sands(selected_topo_data, self.survey_unit, self.date)

        if formatted_topo_data.empty:
            logging.info("Formatted topo data is empty, cannot create SANDS file.")
            return False
        formatted_mater_profile_data, master_profile_outfile = self.format_master_profile_data_for_sands(selected_master_profile_data, self.survey_unit)

        if formatted_mater_profile_data.empty:
            logging.info("Formatted master profile data is empty, cannot create SANDS file.")
            return False

        return True


    def get_topo_data_ready_for_conversion(self, survey_unit: str, date: str) -> pd.DataFrame:
        """Fetch topo data rows for a given survey_unit and date as a DataFrame."""
        conn = establish_connection()
        if not conn:
            raise RuntimeError("Could not connect to the database")

        try:
            query = text("""
                SELECT *
                FROM staging_data.topo_data
                WHERE survey_unit = :survey_unit
                  AND date = :date
               
            """)

            result = conn.execute(query, {"survey_unit": survey_unit, "date": date}).mappings().all()
            df = pd.DataFrame(result)
            return df

        except Exception as e:
            print(f"Error fetching topo data: {e}")
            return pd.DataFrame()  # return empty DataFrame on error
        finally:
            conn.close()

    def get_master_profile_data_ready_for_sands(self, survey_unit: str, date: str,
                                                topo_data_df: pd.DataFrame) -> pd.DataFrame:
        """Fetch master profile data for a given survey_unit and date as a DataFrame."""
        conn = establish_connection()
        if not conn:
            raise RuntimeError("Could not connect to the database")

        selected_profiles = topo_data_df['profile'].unique().tolist()

        if not selected_profiles:
            logging.warning(f"No profiles found in topo data for survey_unit={survey_unit}, date={date}")
            return pd.DataFrame()

        try:
            query = text("""
                SELECT *
                FROM staging_data.master_profiles
                WHERE profile_id = ANY(:selected_profiles);
            """)

            # Pass the profile list directly. Psycopg2 will serialize it to a PostgreSQL array.
            result = conn.execute(query, {"selected_profiles": selected_profiles}).mappings().all()
            df = pd.DataFrame(result)
            return df

        except Exception as e:
            logging.error(f"Error fetching master profile data: {e}", exc_info=True)
            return pd.DataFrame()

        finally:
            conn.close()

    def format_topo_data_for_sands(self, selected_topo_df: pd.DataFrame, survey_unit: str,
                                   date: str):
        """
        Formats topo data into the correct SANDS text file format and writes it to disk.

        Returns:
            formatted_df (pd.DataFrame)
            output_file (str) - full path to generated .txt file
        """

        formatted_df = selected_topo_df[
            ['easting', 'northing', 'elevation_od', 'chainage', 'fc', 'profile', 'reg_id']].copy()

        formatted_df = formatted_df.rename(columns={
            'easting': 'Easting',
            'northing': 'Northing',
            'elevation_od': 'Elevation',
            'chainage': 'Chainage',
            'fc': 'FC',
            'profile': 'Profile',
            'reg_id': 'Reg_ID'
        })

        # Sands format profile is always 'N/A'
        formatted_df['Profile'] = 'N/A'

        # Round numerical values to 3 decimals
        formatted_df = formatted_df.round({
            'Easting': 3,
            'Northing': 3,
            'Elevation': 3,
            'Chainage': 3,
        })

        # Sort by Reg_ID and then by Chainage ascending]
        formatted_df = formatted_df.sort_values(by=['Reg_ID', 'Chainage']).reset_index(drop=True)


        add_date = datetime.now().strftime("%Y-%m-%d")

        # Determine Downloads folder path
        downloads_folder = Path.home() / f"Downloads/SandsData_{add_date}"
        downloads_folder.mkdir(exist_ok=True)  # Ensure directory exists

        # Construct filename
        safe_date = date.replace("-", "")
        output_file = os.path.join(downloads_folder, f"SANDS_TOPO_{survey_unit}_{safe_date}.txt")

        # Save as tab-separated TXT
        formatted_df.to_csv(output_file, index=False, sep='\t')

        return formatted_df, output_file



    def format_master_profile_data_for_sands(self, selected_master_profile_df: pd.DataFrame, survey_unit):



        formatted_df = selected_master_profile_df[
            ['profile_id', 'date', 'chainage', 'elevation']].copy()

        formatted_df = formatted_df.rename(columns={
            'profile_id': 'Profile_ID',
            'date': 'Date',
            'chainage': 'Chainage',
            'elevation': 'Elevation'
        })
        # Round numerical values to 3 decimals
        formatted_df = formatted_df.round({
            'Chainage': 3,
            'Elevation': 3,
        })

        # Sort by chainage ascending
        formatted_df = formatted_df.sort_values(by='Chainage').reset_index(drop=True)

        # get the date from the df and format it
        date = formatted_df['Date'].iloc[0].strftime("%Y-%m-%d")

        add_date = datetime.now().strftime("%Y-%m-%d")

        # Determine Downloads folder path
        downloads_folder = Path.home() / f"Downloads/SandsData_{add_date}"
        downloads_folder.mkdir(exist_ok=True)  # Ensure directory exists

        # Construct filename
        safe_date = date.replace("-", "")
        output_file = os.path.join(downloads_folder, f"SANDS_MP_{survey_unit}_{safe_date}.txt")

        # Ensure output directory exists


        # Save as tab-separated TXT
        formatted_df.to_csv(output_file, index=False, sep='\t')

        return formatted_df, output_file


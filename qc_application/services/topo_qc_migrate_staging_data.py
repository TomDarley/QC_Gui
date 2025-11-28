import logging
import pandas as pd
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlalchemy import text
from qc_application.services.topo_calculate_cpa_service import CalculateCPATool
from qc_application.utils.database_connection import establish_connection

class MigrateStagingToLive:

    def __init__(self, edit_mode = 'qc',  edit_mode_target = None):

        self. conn = None
        self.all_mp_data =None
        self.all_topo_data = None
        self.all_cpa_data = None
        self.changed_mp_profiles = []
        self.edit_mode = edit_mode  # 'qc' or 'edit'
        self.edit_mode_target = edit_mode_target  # (unique_profiles ->list, date) tuple if in 'edit' mode

    def migrate_data(self):
        data_is_valid  =self.verify_data()
        if not data_is_valid:
            logging.error("Data verification failed. Migration aborted.")
            return False
        # Recalculate CPA for changed Master Profiles
        new_cpa_data = self.calculate_addition_cpa_for_changed_mps()
        if not new_cpa_data.empty:
            new_cpa_data.columns = new_cpa_data.columns.str.lower()
            self.all_cpa_data =  pd.concat([self.all_cpa_data, new_cpa_data], ignore_index=True)


        update_successful = self.update_live_tables()

        if update_successful:
            logging.info("Data migration from staging to live tables completed successfully.")
            return True
        else:
            logging.error("Data migration failed during live table update.")
            return False

    def check_all_tables_have_matching_data(self, cpa_df, mp_df, topo_df):
        #Format column headers so comparisons can be made

        all_survey_units = list(cpa_df['survey_unit'].unique())
        all_profiles = list(cpa_df['profile'].unique())

        # check mp has exactly the same profiles as cpa, duplicates are okay
        mp_profiles = list(mp_df['profile_id'].unique())
        for profile in all_profiles:
            if profile not in mp_profiles:
                logging.error(f"Profile {profile} in CPA data not found in Master Profile data.")
                return False


        # check topo has exactly the same survey units as cpa, duplicates are okay
        topo_survey_units = list(topo_df['survey_unit'].unique())
        for survey_unit in all_survey_units:
            if survey_unit not in topo_survey_units:
                logging.error(f"Survey Unit {survey_unit} in CPA data not found in Topo data.")
                return False

        # check topo has exactly the same survey units as cpa, duplicates are okay
        topo_profiles = list(topo_df['profile'].unique())
        for profile in all_profiles:
            if profile not in topo_profiles:
                logging.error(f"Profile {profile} in CPA data not found in Topo data.")
                return False
        return True

    def check_for_mp_changes(self, mp_df):
        # Get list of IDs from incoming data
        all_new_mp_ids = list(mp_df['profile_id'].unique())

        # Query current data from the database
        get_current_mp_data_result = self.conn.execute(text("""
            SELECT *
            FROM topo_qc.master_profiles 
            WHERE profile_id IN :mp_ids
        """), {"mp_ids": tuple(all_new_mp_ids)})

        current_mp_data = pd.DataFrame(
            get_current_mp_data_result.fetchall(),
            columns=get_current_mp_data_result.keys()
        )

        # Ensure both datasets are sorted and column-aligned
        mp_df_sorted = mp_df.sort_values("profile_id").reset_index(drop=True)
        current_mp_data_sorted = current_mp_data.sort_values("profile_id").reset_index(drop=True)

        # If shapes differ, changes exist
        if mp_df_sorted.shape != current_mp_data_sorted.shape:
            logging.info("Master Profile structure changed.")
            return True, None

        # Compare dataframes
        diff = mp_df_sorted.compare(current_mp_data_sorted)

        if diff.empty:
            # No changes detected
            logging.info("No changes in Master Profile data.")
            return False, None

        # Identify changed profile_id values
        changed_profile_ids = mp_df_sorted.loc[diff.index, "profile_id"].unique().tolist()

        logging.info(f"Changes detected in Master Profile data for profile_id(s): {changed_profile_ids}")

        return True, changed_profile_ids

    def verify_data(self):
        # 1) Get Master Profile Data

        if not self.conn:
            try:
                self.conn = establish_connection()
            except Exception as e:
                self.status_label.setText("Error: Could not connect to database")

                return False

        try:

            if self.edit_mode:
                staging_cpa_data_result = self.conn.execute(
                    text("""
                            SELECT *
                            FROM staging_data.cpa_table
                            WHERE profile = ANY(:profile_ids)
                              AND date = :date
                        """),
                    {
                        "profile_ids": self.edit_mode_target[0],  # must be a tuple/list
                        "date": self.edit_mode_target[1]
                    }
                )
            else:

                staging_cpa_data_result = self.conn.execute(text("""
                    SELECT *
                    FROM staging_data.cpa_table
                """))

            self.all_cpa_data = pd.DataFrame(
                staging_cpa_data_result.fetchall(),
                columns=staging_cpa_data_result.keys()
            )

            if self.edit_mode:
                staging_mp_data_result = self.conn.execute(
                    text("""
                        SELECT *
                        FROM staging_data.master_profiles
                        WHERE profile_id = ANY(:profile_ids)
                         
                    """),
                    {
                        "profile_ids": self.edit_mode_target[0],  # must be a tuple/list

                    }
                )
            else:


                staging_mp_data_result = self.conn.execute(text("""
                               SELECT *
                               FROM staging_data.master_profiles
                           """))



            self.all_mp_data = pd.DataFrame(
                staging_mp_data_result.fetchall(),
                columns=staging_mp_data_result.keys()
            )


            if self.edit_mode:
                staging_topo_data_result = self.conn.execute(
                    text("""
                        SELECT *
                        FROM staging_data.topo_data
                        WHERE profile = ANY(:profile_ids)
                          AND date = :date
                    """),
                    {
                        "profile_ids": self.edit_mode_target[0],  # must be a tuple/list
                        "date": self.edit_mode_target[1]
                    }
                )
            else:

                staging_topo_data_result = self.conn.execute(text("""
                                           SELECT *
                                           FROM staging_data.topo_data
                                       """))

            self.all_topo_data = pd.DataFrame(
                staging_topo_data_result.fetchall(),
                columns=staging_topo_data_result.keys()
            )

            if self.all_cpa_data.empty or self.all_mp_data.empty or self.all_topo_data.empty:

                logging.error("One or more staging tables are empty.")
                return False

            print("Staging CPA Data:")
            print(self.all_cpa_data)
            print("Staging Master Profile Data:")
            print(self.all_mp_data)
            print("Staging Topo Data:")
            print(self.all_topo_data)

            match_check = self.check_all_tables_have_matching_data(self.all_cpa_data, self.all_mp_data, self.all_topo_data)
            if not match_check:
                logging.error("Data mismatch between staging tables. Migration aborted.")
                return False
            print(match_check)

            mp_changes_check, changed_profiles = self.check_for_mp_changes(self.all_mp_data)
            print(mp_changes_check, changed_profiles)
            if mp_changes_check:
                self.changed_mp_profiles = changed_profiles
                logging.info("Master Profile changes detected.")

            return True


        except SQLAlchemyError as e:
            logging.error(f"Database query error: {e}")
            return None

    def calculate_addition_cpa_for_changed_mps(self):
        if not self.changed_mp_profiles:
            logging.info("No changed Master Profiles to recalculate CPA for.")
            return pd.DataFrame

        recalculated_cpa_dfs = []

        for profile_id in self.changed_mp_profiles:

            # Get exsiting topo data for this profile
            existing_profile_topo_data_result  = self.conn.execute(text(""" 
                SELECT *
                FROM topo_qc.topo_data
                WHERE profile = :profile_id
            """), {"profile_id": profile_id})
            existing_profile_topo_data = pd.DataFrame(
                existing_profile_topo_data_result.fetchall(),
                columns=existing_profile_topo_data_result.keys()
            )

            unique_survey_dates = existing_profile_topo_data['date'].unique()
            for survey_date in unique_survey_dates:
                profile_topo_data = existing_profile_topo_data[existing_profile_topo_data['date'] == survey_date]

                # Get Master Profile data for this profile
                master_profile_data = self.all_mp_data[self.all_mp_data['profile_id'] == profile_id]

                # Recalculate CPA
                cpa_tool = CalculateCPATool(
                    survey_unit=profile_topo_data['survey_unit'].iloc[0],
                    profile=profile_id,
                    master_profile_data= master_profile_data,
                    new_profile_data= profile_topo_data,
                    survey_date = survey_date
                )
                recalculated_cpa_df = cpa_tool.calculate_cpa()
                recalculated_cpa_dfs.append(recalculated_cpa_df)

        all_new_cpa_data = pd.concat(recalculated_cpa_dfs, ignore_index=True)
        return all_new_cpa_data

    def update_live_tables(self):

        # Ensure DB connection exists
        if not self.conn:
            try:
                self.conn = establish_connection()
            except Exception:
                logging.error("Error: Could not connect to database")
                return False

        engine = self.conn.engine  # SQLAlchemy engine reference

        try:
            with engine.begin() as conn:  # Atomic transaction

                # ----------------------------------------------------------------------
                # 1) UPSERT CPA DATA
                # ----------------------------------------------------------------------
                insert_cpa_sql = text("""
                    INSERT INTO topo_qc.cpa_table (survey_unit, date, profile, area)
                    VALUES (:survey_unit, :date, :profile, :area)
                    ON CONFLICT (survey_unit, date, profile)
                    DO UPDATE SET area = EXCLUDED.area
                """)
                conn.execute(insert_cpa_sql, self.all_cpa_data.to_dict(orient='records'))

                # ----------------------------------------------------------------------
                # 2) UPDATE MASTER PROFILES
                # ----------------------------------------------------------------------
                if self.changed_mp_profiles:

                    delete_mp_sql = text("""
                        DELETE FROM topo_qc.master_profiles 
                        WHERE profile_id = :profile_id
                    """)

                    insert_mp_sql = text("""
                        INSERT INTO topo_qc.master_profiles 
                        (profile_id, date, chainage, elevation, sequence)
                        VALUES (:profile_id, :date, :chainage, :elevation, :sequence)
                    """)

                    for profile_id in self.changed_mp_profiles:
                        conn.execute(delete_mp_sql, {"profile_id": profile_id})

                        profile_data = (
                            self.all_mp_data[self.all_mp_data['profile_id'] == profile_id]
                            .copy()
                        )
                        profile_data['sequence'] = profile_data['sequence'].apply(
                            lambda x: int(x) if pd.notna(x) else None
                        )

                        conn.execute(insert_mp_sql, profile_data.to_dict(orient='records'))

                # ----------------------------------------------------------------------
                # 3) UPSERT TOPO DATA (ONLY UPDATE IF CHANGED)
                # ----------------------------------------------------------------------
                insert_topo_sql = text("""
                    INSERT INTO topo_qc.topo_data
                    (easting, northing, elevation_od, chainage, fc, profile, reg_id,
                     survey_unit, date, year, month)
                    VALUES (:easting, :northing, :elevation_od, :chainage, :fc, :profile,
                            :reg_id, :survey_unit, :date, :year, :month)
                    ON CONFLICT (profile, date, chainage)
                    DO UPDATE SET
                        easting      = EXCLUDED.easting,
                        northing     = EXCLUDED.northing,
                        elevation_od = EXCLUDED.elevation_od,
                        fc           = EXCLUDED.fc,
                        reg_id       = EXCLUDED.reg_id,
                        survey_unit  = EXCLUDED.survey_unit,
                        year         = EXCLUDED.year,
                        month        = EXCLUDED.month
                    WHERE
                        topo_qc.topo_data.easting      IS DISTINCT FROM EXCLUDED.easting OR
                        topo_qc.topo_data.northing     IS DISTINCT FROM EXCLUDED.northing OR
                        topo_qc.topo_data.elevation_od IS DISTINCT FROM EXCLUDED.elevation_od OR
                        topo_qc.topo_data.fc           IS DISTINCT FROM EXCLUDED.fc OR
                        topo_qc.topo_data.reg_id       IS DISTINCT FROM EXCLUDED.reg_id OR
                        topo_qc.topo_data.survey_unit  IS DISTINCT FROM EXCLUDED.survey_unit OR
                        topo_qc.topo_data.year         IS DISTINCT FROM EXCLUDED.year OR
                        topo_qc.topo_data.month        IS DISTINCT FROM EXCLUDED.month;
                """)

                conn.execute(insert_topo_sql, self.all_topo_data.to_dict(orient='records'))

                # ----------------------------------------------------------------------
                # 4) Update QC Log (only outside edit mode)
                # ----------------------------------------------------------------------
                if self.edit_mode != 'edit':
                    unique_survey_dates = (
                        self.all_topo_data[['survey_unit', 'date']].drop_duplicates()
                    )

                    update_qc_log_sql = text("""
                        UPDATE topo_qc.qc_log
                        SET pushed_to_dash = TRUE
                        WHERE survey_unit = :survey_unit AND completion_date = :date
                    """)

                    for _, row in unique_survey_dates.iterrows():
                        conn.execute(update_qc_log_sql, {
                            'survey_unit': row['survey_unit'],
                            'date': row['date']
                        })

                # ----------------------------------------------------------------------
                # 5) CLEAR STAGING TABLES (column names differ by table)
                # ----------------------------------------------------------------------
                profile_ids = self.all_topo_data['profile'].unique().tolist()
                dates = self.all_topo_data['date'].unique().tolist()

                # Tables that use "profile"
                tables_with_profile = [
                    "cpa_table",
                    "cpa_table_history",
                    "topo_data",
                    "topo_data_history"
                ]

                # Tables that use "profile_id"
                tables_with_profile_id = [
                    "master_profiles",
                    "master_profiles_history"
                ]

                delete_profile_sql = text("""
                    DELETE FROM staging_data.{table}
                    WHERE profile = ANY(:profiles)
                    AND date = ANY(:dates)
                """)
                for table in tables_with_profile:
                    conn.execute(
                        text(delete_profile_sql.text.format(table=table)),
                        {"profiles": profile_ids, "dates": dates}
                    )

                mp_profile_ids = self.all_mp_data['profile_id'].unique().tolist()
                delete_profile_id_sql = text("""
                    DELETE FROM staging_data.{table}
                    WHERE profile_id = ANY(:profile_ids)
                    AND date = ANY(:dates)
                """)
                for table in tables_with_profile_id:
                    conn.execute(
                        text(delete_profile_id_sql.text.format(table=table)),
                        {"profile_ids": mp_profile_ids, "dates": dates}
                    )

            # All operations succeeded (commit happens automatically)
            logging.info("Live tables updated successfully and staging cleared.")
            return True

        except Exception as e:
            logging.error(f"Database update failed. All changes rolled back. Error: {e}")
            return False



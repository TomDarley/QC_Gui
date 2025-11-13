from datetime import datetime
import logging
from qc_application.utils.database_connection import establish_connection
from sqlalchemy import text

class SurveyChecker:
    def __init__(self):
        self.valid_check_values = ["Pass", "Resolved", "Omitted"]
        self.date_fields = [
            "completion_date", "survey_received", "gen_date_checked", "pps_date_checked"
        ]
        self.values_requiring_comment = ["Omitted", "Failed", "Rejected", "Issue"]

    def is_valid_date(self, value):
        if value is None:
            return False
        try:
            datetime.strptime(str(value), "%Y-%m-%d")
            return True
        except ValueError:
            return False

    def is_comment_required(self, main_val, comment_val):
        return (main_val in self.values_requiring_comment) and not comment_val

    def is_field_invalid(self, field, value):
        if field in self.date_fields:
            return not self.is_valid_date(value)
        return value is None or str(value).strip() == ""

    from sqlalchemy import text
    import logging

    def check_survey_complete(self, survey_type, index):
        """Check whether a survey record is complete in the QC log."""
        try:
            # --- Define field groups ---
            interim_fields = [
                "survey_unit", "survey_type", "completion_date", "survey_received",
                "delivery_reference",
                "gen_data_labelling", "gen_data_labelling_ic",
                "gen_data_filename", "gen_data_filename_ic",
                "gen_metadata", "gen_metadata_ic",
                "gen_survey_report", "gen_survey_report_ic",
                "gen_control_observations", "gen_control_observations_ic",
                "gen_added_to_high_level_planner", "gen_added_to_high_level_planner_ic",
                "gen_date_checked", "gen_name",
                "data_profile_xyz_txt", "data_profile_xyz_txt_ic",
                "checks_pl_on_correct_profile_lines", "checks_pl_on_correct_profile_lines_ic",
                "checks_pl_point_spacing", "checks_pl_point_spacing_ic",
                "checks_pl_seaward_limit", "checks_pl_seaward_limit_ic",
                "checks_pl_profile_start_position", "checks_pl_profile_start_position_ic",
                "checks_pl_offline_variation", "checks_pl_offline_variation_ic",
                "checks_name", "sands_profiles_imported", "sands_profiles_imported_ic",
                "sands_checked", "sands_checked_ic",
                "sands_profiles_acceptable", "sands_profiles_acceptable_ic",
                "sands_loaded_to_ea", "sands_loaded_to_ea_ic",
                "sands_added_to_upload_log", "sands_added_to_upload_log_ic",
            ]

            post_storm_fields = interim_fields + [
                "pps_profile_data", "pps_profile_data_ic",
                "pps_profile_other_data", "pps_profile_other_data_ic",
                "pps_profile_photos", "pps_profile_photos_ic",
                "pps_date_checked", "pps_name",
            ]

            baseline_fields = interim_fields + [
                "data_baseline_xyz_txt", "data_baseline_xyz_txt_ic",
                "data_raster_grid", "data_raster_grid_ic",
                "checks_cd_gaps_greater_than_spec", "checks_cd_gaps_greater_than_spec_ic",
                "checks_cd_seaward_limit", "checks_cd_seaward_limit_ic",
                "checks_cd_ascii_created_split", "checks_cd_ascii_created_split_ic",
            ]

            # --- Connect using SQLAlchemy ---
            conn = establish_connection()
            if not conn:
                return {
                    "index": index,
                    "survey_type": survey_type,
                    "incomplete_fields": [],
                    "error": "Database connection failed",
                }

            # --- Fetch only the specific row by OFFSET (efficient) ---
            query = text("SELECT * FROM topo_qc.qc_log OFFSET :idx LIMIT 1;")
            result = conn.execute(query, {"idx": index})
            row = result.fetchone()

            if not row:
                return {
                    "index": index,
                    "survey_type": survey_type,
                    "incomplete_fields": [],
                    "error": "Index out of range",
                }

            colnames = result.keys()
            row_dict = dict(zip(colnames, row))

            # --- Choose correct field list ---
            survey_type_lower = survey_type.lower()
            if survey_type_lower in ["spring interim", "autumn interim"]:
                fields = interim_fields
            elif survey_type_lower == "post storm":
                fields = post_storm_fields
            else:
                fields = baseline_fields

            incomplete_fields = []

            # --- Validate fields ---
            for field in fields:
                if field.endswith("_ic"):
                    related_field = field[:-2]
                    main_val = row_dict.get(related_field)
                    comment_val = row_dict.get(field)
                    if self.is_comment_required(main_val, comment_val):
                        incomplete_fields.append(field)
                else:
                    if self.is_field_invalid(field, row_dict.get(field)):
                        incomplete_fields.append(field)

            return {
                "index": index,
                "survey_type": survey_type,
                "incomplete_fields": incomplete_fields,
            }

        except Exception as e:
            logging.exception("Error in check_survey_complete")
            return {
                "index": index,
                "survey_type": survey_type,
                "incomplete_fields": [],
                "error": str(e),
            }

        finally:
            try:
                if "conn" in locals() and conn:
                    conn.close()
            except Exception:
                pass


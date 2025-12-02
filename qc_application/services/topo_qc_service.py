import shutil
import logging
from dataclasses import dataclass
from typing import List, Dict, Optional

try:
    from qc_application.config.app_settings import AppSettings
except ImportError as e:
    logging.error(f"Failed to import AppSettings: {str(e)}")

settings = AppSettings()
ARCGIS_TEMPLATE_PATH = settings.get("arcgis_template_path")
ARCGIS_PRO_PATH = settings.get("arcgis_pro_path")

try:
    import arcpy
    from arcpy import env
except RuntimeError as re:
    raise ImportError("ArcPy could not be imported.") from re

import sys
import subprocess
import tempfile
import os
from pathlib import Path

try:
    from qc_application.utils.main_qc_tool_helper_functions import *
    from qc_application.dependencies import mlsw_dict
    from qc_application.dependencies.system_paths import OS_TILES_PATH
except ImportError as e:
    raise ImportError("Helper functions could not be imported.") from e

logging.basicConfig(
    level=logging.INFO,
    format='%(message)s',
    stream=sys.stdout,
    force=True
)


@dataclass
class SurveyResult:
    """Tracks the result of processing a single survey."""
    file_path: str
    survey_unit: str = ""
    success: bool = False
    error_message: str = ""
    stage: str = ""  # Which stage failed


class TopoQCTool:
    os_tiles_path = OS_TILES_PATH

    def __init__(self, input_text_files, interim_survey_lines):
        self.input_text_files = [f.strip() for f in input_text_files.split(';') if f.strip()]
        self.interim_survey_lines = interim_survey_lines

        logging.info(f"Input files: {self.input_text_files}")
        logging.info(f"Interim Survey Lines: {self.interim_survey_lines}")

        self.outputs_for_map = {}
        self.survey_results: List[SurveyResult] = []

    def run_topo_qc(self) -> Dict[str, any]:
        """
        Run QC on all input files and return detailed results.

        Returns:
            dict: Contains 'success_count', 'failed_count', 'results' list
        """
        env.overwriteOutput = True
        spacing_unit_error = 2.5

        for input_text_file in self.input_text_files:
            result = SurveyResult(file_path=input_text_file)

            try:
                success = self._process_single_survey(
                    input_text_file,
                    spacing_unit_error,
                    result
                )
                result.success = success

            except Exception as e:
                result.success = False
                result.error_message = str(e)
                result.stage = result.stage or "Unknown"
                logging.error(f"Failed processing {input_text_file}: {str(e)}")

            finally:
                self.survey_results.append(result)

        # Generate summary
        success_count = sum(1 for r in self.survey_results if r.success)
        failed_count = len(self.survey_results) - success_count

        logging.info(f"\n{'=' * 60}")
        logging.info(f"QC PROCESSING COMPLETE")
        logging.info(f"{'=' * 60}")
        logging.info(f"Total surveys: {len(self.survey_results)}")
        logging.info(f"Successful: {success_count}")
        logging.info(f"Failed: {failed_count}")

        if failed_count > 0:
            logging.info(f"\nFailed surveys:")
            for r in self.survey_results:
                if not r.success:
                    logging.info(
                        f"  - {r.survey_unit or os.path.basename(r.file_path)}: {r.error_message} (Stage: {r.stage})")

        # Only display map if at least one survey succeeded
        if success_count > 0:
            try:
                self._display_findings_on_map(self.outputs_for_map)
            except Exception as e:
                logging.error(f"Failed to display results on map: {str(e)}")

        return {
            'success_count': success_count,
            'failed_count': failed_count,
            'results': self.survey_results,
            'total': len(self.survey_results)
        }

    def _process_single_survey(self, input_text_file: str, spacing_unit_error: float,
                               result: SurveyResult) -> bool:
        """
        Process a single survey file. Returns True on success, False on failure.
        Updates the result object with progress information.
        """
        logging.info(f"\n{'=' * 60}")
        logging.info(f"Processing: {os.path.basename(input_text_file)}")
        logging.info(f"{'=' * 60}")

        input_text = input_text_file

        # Check file exists
        result.stage = "File Validation"
        if not os.path.exists(input_text_file):
            result.error_message = "File not found"
            logging.error(f"File not found: {input_text_file}")
            return False

        data_profile_xyz = "Pass"
        data_profile_xyz_c = "Found"
        survey_profile_lines_shp = self.interim_survey_lines

        # Extract baseline survey flag
        result.stage = "Survey Type Detection"
        bool_baseline_survey = is_baseline_survey(input_text)
        logging.info(f"Baseline Survey: {bool_baseline_survey}")

        # Extract survey unit
        result.stage = "Survey Unit Extraction"
        extracted_survey_unit = get_input_survey_unit(input_text, survey_profile_lines_shp)
        if not extracted_survey_unit:
            result.error_message = "Could not extract survey unit from file path"
            logging.warning(f"Skipping: {result.error_message}")
            return False

        result.survey_unit = extracted_survey_unit

        file_friendly_survey_unit = make_file_friendly_survey_unit(extracted_survey_unit)

        # Extract cell
        result.stage = "Cell Extraction"
        extracted_cell = get_survey_cell(input_text_file, survey_profile_lines_shp)
        if not extracted_cell:
            result.error_message = "Could not extract cell from file path"
            logging.warning(f"Skipping: {result.error_message}")
            return False

        # Get survey completion date
        result.stage = "Date Extraction"
        survey_completion_date = get_survey_completion_date(input_text)
        if not survey_completion_date:
            result.error_message = "Could not extract survey completion date"
            logging.warning(f"Skipping: {result.error_message}")
            return False

        survey_type = define_survey_type(survey_completion_date, bool_baseline_survey)

        # Update high level planner
        result.stage = "High Level Planner Update"
        long_survey_unit = extracted_cell + extracted_survey_unit
        complete_high_level_planner = update_high_level_planner(
            survey_type=survey_type,
            survey_unit=long_survey_unit,
            survey_completion_date=survey_completion_date,
            mode="Fill"
        )
        if not complete_high_level_planner:
            result.error_message = "Failed to update high level planner"
            logging.error(f"Skipping: {result.error_message}")
            # Attempt revert but continue
            try:
                update_high_level_planner(
                    survey_type=survey_type,
                    survey_unit=long_survey_unit,
                    survey_completion_date=survey_completion_date,
                    mode="Revert"
                )
            except:
                pass
            return False

        # Set workspace
        result.stage = "Workspace Setup"
        set_workspace = get_qc_workspace(input_text)
        if not set_workspace:
            result.error_message = "Could not set workspace"
            logging.error(f"Skipping: {result.error_message}")
            return False

        env.workspace = workspace = set_workspace

        # Convert text file
        result.stage = "Text File Conversion"
        standardised_df = universal_text_file_converter(input_text)
        if len(standardised_df) == 0:
            result.error_message = "Could not parse input text file"
            logging.error(f"Skipping: {result.error_message}")
            return False

        # Get MLSW
        result.stage = "MLSW Retrieval"
        MLSW = get_mlsw(extracted_survey_unit, extracted_cell, mlsw_dict.mlsw_dict)

        # Create point file
        result.stage = "Point File Creation"
        points_file_name = create_point_file_name(extracted_cell, file_friendly_survey_unit, survey_completion_date)
        points_file_path = make_xy_event_layer(standardised_df, workspace, points_file_name)

        # Feature code check
        result.stage = "Feature Code Validation"
        bad_feature_code_dict = feature_code_check(standardised_df)

        # Extract interim lines
        result.stage = "Interim Lines Extraction"
        selected_interim_lines = extract_interim_lines(
            survey_profile_lines_shp,
            workspace,
            extracted_cell,
            file_friendly_survey_unit,
            bool_baseline_survey
        )

        region = get_region(input_text)

        # Create offline buffer
        result.stage = "Offline Buffer Creation"
        offline_line_buffer_path = create_offline_buffer_file_name(
            region, workspace, extracted_cell, file_friendly_survey_unit
        )
        create_offline_buffer(region, offline_line_buffer_path, selected_interim_lines)

        # Get offline points
        result.stage = "Offline Points Detection"
        offline_points_path = generate_offline_points_path(workspace, extracted_cell, file_friendly_survey_unit)
        offline_points = get_offline_points(
            points_file_path, offline_line_buffer_path, standardised_df,
            offline_points_path, workspace
        )

        # Create distance buffer
        result.stage = "Distance Buffer Creation"
        buffer_file_path = generate_buffer_output_path(workspace, extracted_cell, file_friendly_survey_unit)
        create_distance_buffer(points_file_path, buffer_file_path, spacing_unit_error)

        # Spacing check
        result.stage = "Spacing Check"
        lengths_over_spec = spacing_check(standardised_df, spacing_unit_error)

        # Depth check
        result.stage = "Depth Check"
        depth_checks = check_made_depth(standardised_df, MLSW)

        # Profile line check
        result.stage = "Profile Line Check"
        points_lie_on_correct_profile = check_points_lie_on_correct_profile_lines(
            points_file_path, offline_line_buffer_path
        )

        # Extract survey metadata
        result.stage = "Metadata Extraction"
        survey_meta = extract_survey_meta(
            input_text, extracted_survey_unit, survey_completion_date,
            survey_type, extracted_cell, bool_baseline_survey,
            lengths_over_spec, depth_checks, offline_points, set_workspace,
            data_profile_xyz_c, points_lie_on_correct_profile, complete_high_level_planner
        )

        # Photo checks
        result.stage = "Photo Validation"
        survey_meta = run_photo_checks(
            selected_interim_lines, survey_completion_date, input_text_file,
            bool_baseline_survey, survey_meta
        )

        # Baseline checks
        xy_point_layer_path = None
        ras1_path = None
        aggregate_points_path = None
        mask_path = None
        hillshade_path = None

        if bool_baseline_survey:
            result.stage = "Baseline Checks"
            xy_point_layer_path, ras1_path, aggregate_points_path, mask_path, hillshade_path = \
                run_baseline_checks(input_text_file, workspace, survey_meta, bool_baseline_survey)

        # Push to database
        result.stage = "Database Push"
        push_result = push_results_to_database(survey_meta, input_text_file, region, bool_baseline_survey)
        if not push_result:
            result.error_message = "Failed to push results to database"
            logging.error(f"Skipping: {result.error_message}")
            return False

        # Generate report
        result.stage = "Report Generation"
        generate_report(
            offline_points, lengths_over_spec, depth_checks,
            bad_feature_code_dict, workspace, extracted_survey_unit
        )

        # Log paths for map
        result.stage = "Map Output Logging"
        new_outputs = log_paths_to_add_to_map(
            extracted_survey_unit,
            bool_baseline_survey,
            points_file_path,
            offline_line_buffer_path,
            offline_points_path,
            buffer_file_path,
            xy_point_layer_path,
            ras1_path,
            aggregate_points_path,
            mask_path,
            hillshade_path
        )

        # Merge into main dict
        for key, value in new_outputs.items():
            if key in self.outputs_for_map:
                self.outputs_for_map[key].extend(value)
            else:
                self.outputs_for_map[key] = value

        logging.info(f"✅ Successfully processed: {extracted_survey_unit}")
        return True

    def _display_findings_on_map(self, outputs_for_map):
        """Display generated shapefiles on the map."""

        def get_downloads_folder():
            user_profile = os.getenv('USERPROFILE')
            downloads_folder = os.path.join(user_profile, "Downloads")
            if os.path.exists(downloads_folder):
                logging.info(f"Found Downloads folder at {downloads_folder}")
                return downloads_folder
            else:
                raise FileNotFoundError("Downloads folder not found.")

        def create_aprx_file(aprx_path):
            try:
                template_path = Path(ARCGIS_TEMPLATE_PATH)
                shutil.copy(template_path, aprx_path)
                logging.info(f"New ArcGIS project saved at {aprx_path}")
                return arcpy.mp.ArcGISProject(aprx_path)
            except Exception as e:
                logging.error(f"Failed to create .aprx file: {str(e)}")
                return None

        def create_empty_group_layer(aprx):
            try:
                map_obj = aprx.listMaps()[0]
                temp_group_layer = map_obj.createGroupLayer("TEMP_GROUP")
                temp_lyrx = os.path.join(tempfile.gettempdir(), "empty_group.lyrx")
                temp_group_layer.saveACopy(temp_lyrx)
                map_obj.removeLayer(temp_group_layer)
                return temp_lyrx
            except Exception as e:
                logging.error(f"Failed to create empty group layer: {str(e)}")
                return None

        def add_shapefiles_to_map(aprx, outputs_for_map):
            try:
                map_obj = aprx.listMaps("*")[0]
                empty_group_lyrx = create_empty_group_layer(aprx)

                for group_name, shapefiles in outputs_for_map.items():
                    group_layer = map_obj.addLayer(arcpy.mp.LayerFile(empty_group_lyrx), "TOP")[0]
                    group_layer.name = group_name
                    logging.info(f"Created group layer '{group_name}'")

                    for shp in shapefiles:
                        if shp is not None and os.path.exists(shp):
                            try:
                                lyr = map_obj.addDataFromPath(shp)
                                if lyr:
                                    logging.info(f"Added {shp} to group '{group_name}'")
                                    map_obj.addLayerToGroup(group_layer, lyr, "BOTTOM")
                                    map_obj.removeLayer(lyr)
                                else:
                                    logging.error(f"Layer failed to load: {shp}")
                            except Exception as e:
                                logging.error(f"Error adding {shp}: {str(e)}")
                        else:
                            logging.warning(f"Invalid shapefile path: {shp}")

                aprx.save()
            except Exception as e:
                logging.error(f"Failed to add shapefiles to map: {str(e)}")

        def launch_arcgis_pro(aprx_path):
            try:
                arcgis_pro_path = Path(ARCGIS_PRO_PATH)
                if not os.path.exists(arcgis_pro_path):
                    logging.error(f"ArcGIS Pro not found at {arcgis_pro_path}")
                    return
                subprocess.Popen([arcgis_pro_path, aprx_path])
                logging.info(f"Opening ArcGIS Pro: {aprx_path}")
            except Exception as e:
                logging.error(f"Failed to open ArcGIS Pro: {str(e)}")

        # Main execution
        downloads_folder = get_downloads_folder()
        aprx_path = os.path.join(downloads_folder, "Topo_QC_2025.aprx")
        aprx = create_aprx_file(aprx_path)

        if aprx:
            add_shapefiles_to_map(aprx, outputs_for_map)
            launch_arcgis_pro(aprx_path)
        else:
            logging.error("Failed to create ArcGIS project.")


f= TopoQCTool(r'I:\Data\Survey_Topo\Phase4\TSW04\7e\7eSU17-2 Portishead\7eSU17-2_20250211tip\Batch', r'C:\Users\darle\PycharmProjects\QC_Gui\qc_application\dependencies\SW_PROFILES_PHASE4_ALL')
f.run_topo_qc()
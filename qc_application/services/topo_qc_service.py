import shutil
import logging
#from qc_application.config.settings import ARCGIS_TEMPLATE_PATH

try:
    from qc_application.config.app_settings import AppSettings
except ImportError as e:
    logging.error(f"Failed to import TopoQCTool: {str(e)}")



settings = AppSettings()
ARCGIS_TEMPLATE_PATH = settings.get("arcgis_template_path")
ARCGIS_PRO_PATH = settings.get("arcgis_pro_path")


try:
    import arcpy
    from arcpy import env
except RuntimeError as re:
    raise ImportError("ArcPy could not be imported. Ensure that ArcGIS Pro is installed and the Python environment is correctly set up.") from re

import sys
import logging



import subprocess
import tempfile


try:
    from qc_application.utils.main_qc_tool_helper_functions import  *
    from qc_application.dependencies import mlsw_dict
    from qc_application.dependencies.system_paths import OS_TILES_PATH
except ImportError as e:
    raise ImportError("Helper functions could not be imported. Ensure that the utils module is accessible.") from e


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(message)s',  # No prefix like "INFO:", just plain messages
    stream=sys.stdout,     # Output to stdout (not stderr)
    force=True             # Override any previous logging config (Python 3.8+)
)


# TODO: Add a method to check if this survey has already had a QC.


class TopoQCTool:

    # used to split OS tiles for baseline surveys
    os_tiles_path = OS_TILES_PATH

    def __init__(self, input_text_files, interim_survey_lines):

        self.input_text_files = [f.strip() for f in input_text_files.split(';') if f.strip()]

        self.interim_survey_lines = interim_survey_lines
        logging.info(f"Input files: {self.input_text_files}")
        logging.info(f"Interim Survey Lines: {self.interim_survey_lines}")

        self.outputs_for_map= {}

        self.qc_successful = False


    def run_topo_qc(self):
        """The source code of the tool. This first block extracts the region, whether its a file made by PCO, the
                Survey Unit, and Cell from the input text file path"""

        try:

            # Allow for existing shapefiles to be overwritten
            env.overwriteOutput = True

            # unit used as the maximum spacing error allowed between surveyed points
            spacing_unit_error = 2.5

            for input_text_file in self.input_text_files:

                input_text = input_text_file

                if os.path.exists(input_text_file):
                    data_profile_xyz = "Pass"
                    data_profile_xyz_c = "Found"
                else:
                    data_profile_xyz = "Issue"
                    data_profile_xyz_c = "Missing"

                # path set in tool to Phase 4 topo lines shapefile
                survey_profile_lines_shp = self.interim_survey_lines

                # Getting baseline parameter boolean input as text returns 'true' or 'false' not true pythonic boolean
                bool_baseline_survey =  is_baseline_survey(input_text)
                logging.info(f"Baseline Survey set to:{bool_baseline_survey}")



                extracted_survey_unit = get_input_survey_unit(input_text, survey_profile_lines_shp)
                if not extracted_survey_unit:
                    logging.warning(f"Extracted Survey Unit could not be set from input text file path: {input_text}. Skipping this file.")
                    break

                file_friendly_survey_unit = make_file_friendly_survey_unit(extracted_survey_unit)
                extracted_cell = get_survey_cell(input_text_file, survey_profile_lines_shp)
                if not extracted_cell:
                    logging.warning(
                        f"Extracted Cell could not be set from input text file path: {input_text}. Skipping this file.")
                    break

                survey_completion_date = get_survey_completion_date(input_text)
                arcpy.AddMessage("Survey Date Selected " + survey_completion_date)

                survey_type = define_survey_type(survey_completion_date, bool_baseline_survey)

                # We fill in the high level planner here, if an error occurs the code will set the qc field to issue
                long_survey_unit = extracted_cell+extracted_survey_unit
                complete_high_level_planner = update_high_level_planner(survey_type = survey_type,
                                                                        survey_unit=long_survey_unit,
                                                                        survey_completion_date=survey_completion_date,
                                                                        mode ="Fill"
                                                                        )
                if not complete_high_level_planner:
                    logging.error(f"High level planner could not be completed for {input_text}. Skipping this file.")
                    break

                set_workspace  = get_qc_workspace(input_text)
                if not set_workspace:
                    logging.error(f"Workspace environment could not be set. Skipping {input_text}.")
                    break

                env.workspace = workspace = set_workspace

                standardised_df = universal_text_file_converter(input_text)
                if len(standardised_df)==0:
                    logging.error(f"Standardised text file data could not be created from {input_text}. Skipping this file.")
                    break

                MLSW = get_mlsw(extracted_survey_unit, extracted_cell, mlsw_dict.mlsw_dict)

                points_file_name = create_point_file_name(extracted_cell, file_friendly_survey_unit, survey_completion_date)

                points_file_path = make_xy_event_layer(standardised_df, workspace,  points_file_name )

                bad_feature_code_dict = feature_code_check(standardised_df)

                selected_interim_lines = extract_interim_lines(
                    survey_profile_lines_shp,
                    workspace,
                    extracted_cell,
                    file_friendly_survey_unit,
                    bool_baseline_survey)

                region  = get_region(input_text)

                offline_line_buffer_path = create_offline_buffer_file_name(region, workspace, extracted_cell, file_friendly_survey_unit)

                create_offline_buffer(region, offline_line_buffer_path, selected_interim_lines)

                offline_points_path = generate_offline_points_path(workspace, extracted_cell, file_friendly_survey_unit)

                offline_points = get_offline_points(points_file_path, offline_line_buffer_path, standardised_df,
                                   offline_points_path, workspace)

                buffer_file_path = generate_buffer_output_path(workspace, extracted_cell, file_friendly_survey_unit)

                create_distance_buffer(points_file_path, buffer_file_path, spacing_unit_error)

                lengths_over_spec = spacing_check(standardised_df, spacing_unit_error)

                depth_checks  =check_made_depth(standardised_df, MLSW)



                points_lie_on_correct_profile = check_points_lie_on_correct_profile_lines(points_file_path, offline_line_buffer_path)


                survey_meta = extract_survey_meta(input_text, extracted_survey_unit, survey_completion_date,
                                        survey_type, extracted_cell, bool_baseline_survey,
                                        lengths_over_spec, depth_checks, offline_points, set_workspace,
                                        data_profile_xyz_c, points_lie_on_correct_profile, complete_high_level_planner)

                # Running photo checks this modifies the meta
                survey_meta =  run_photo_checks(selected_interim_lines, survey_completion_date, input_text_file,
                                 bool_baseline_survey, survey_meta)


                # Running specific baseline checks:
                xy_point_layer_path = None
                ras1_path= None
                aggregate_points_path = None
                mask_path = None
                hillshade_path = None
                if bool_baseline_survey:

                    xy_point_layer_path, ras1_path, aggregate_points_path, mask_path, hillshade_path = run_baseline_checks(input_text_file, workspace, survey_meta, bool_baseline_survey)

                push_result = push_results_to_database(survey_meta, input_text_file, region, bool_baseline_survey)
                if not push_result:
                    logging.error(f"Survey results could not be pushed to the database for {input_text}. Skipping report generation.")
                    self.qc_successful = False
                    return self.qc_successful



                generate_report(offline_points, lengths_over_spec, depth_checks, bad_feature_code_dict, workspace, extracted_survey_unit)

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

                # Merge into the main dict
                for key, value in new_outputs.items():
                    if key in self.outputs_for_map:
                        self.outputs_for_map[key].extend(value)
                    else:
                        self.outputs_for_map[key] = value

            self.qc_successful = True

        except Exception as e:
            self.qc_successful = False
            logging.error(f"An error occurred during the QC process: {str(e)}")

            try:
                logging.info("Attempting to revert high level planner changes...")


            except Exception as e:
                logging.error(f"Failed to revert high level planner changes: {str(e)}")



            return  self.qc_successful

        def displayFindingsOnMap(outputs_for_map):
            """This function controls whether or not generated shapefiles are to be added to the user's current map."""

            def get_downloads_folder():
                user_profile = os.getenv('USERPROFILE')
                downloads_folder = os.path.join(user_profile, "Downloads")
                if os.path.exists(downloads_folder):
                    logging.info(f"Found Downloads folder at {downloads_folder}")
                    return downloads_folder
                else:
                    raise FileNotFoundError("The Downloads folder could not be found.")

            def create_aprx_file(aprx_path):
                try:
                    template_path = Path(ARCGIS_TEMPLATE_PATH)
                    shutil.copy(template_path, aprx_path)
                    logging.info(f"New ArcGIS project saved at {aprx_path}")
                    return arcpy.mp.ArcGISProject(aprx_path)
                except Exception as e:
                    logging.error(f"Failed to create .aprx file: {str(e)}")
                    self.qc_successful= False
                    return

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
                    self.qc_successful= False
                    return

            def add_shapefiles_to_map(aprx, outputs_for_map):
                try:
                    map_obj = aprx.listMaps("*")[0]
                    empty_group_lyrx = create_empty_group_layer(aprx)

                    for group_name, shapefiles in outputs_for_map.items():


                        group_layer = map_obj.addLayer(arcpy.mp.LayerFile(empty_group_lyrx), "TOP")[0]
                        group_layer.name = extracted_cell+group_name
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
                                        logging.error(f"Layer failed to load from: {shp}")
                                except Exception as e:
                                    logging.error(f"Error adding {shp} to group: {str(e)}")

                            else:
                                logging.warning(f"Shapefile path is invalid or not found: {shp}")
                                self.qc_successful = False

                    aprx.save()
                except Exception as e:
                    self.qc_successful = False
                    logging.error(f"Failed to add shapefiles to map: {str(e)}")

            def launch_arcgis_pro(aprx_path):
                try:
                    arcgis_pro_path = Path(ARCGIS_PRO_PATH)
                    if not os.path.exists(arcgis_pro_path):
                        logging.error(f"ArcGIS Pro executable not found at {arcgis_pro_path}")
                        return
                    subprocess.Popen([arcgis_pro_path, aprx_path])
                    logging.info(f"Opening ArcGIS Pro with project: {aprx_path}")
                except Exception as e:
                    self.qc_successful = False
                    logging.error(f"Failed to open ArcGIS Pro project: {str(e)}")

            # Main execution
            downloads_folder = get_downloads_folder()
            aprx_path = os.path.join(downloads_folder, "Topo_QC_2025.aprx")
            aprx = create_aprx_file(aprx_path)

            if aprx:
                add_shapefiles_to_map(aprx, outputs_for_map)
                launch_arcgis_pro(aprx_path)
                self.qc_successful = True

            else:
                logging.error("Failed to create or open ArcGIS project.")

        if not  self.qc_successful:
            return self.qc_successful

        displayFindingsOnMap(self.outputs_for_map)
        return self.qc_successful




#def main():
#    try:
#        topo_tool = TopoQCTool(input_text_files=r"X:\Data\Survey_Topo\Phase4\TSW02\6d\6d6D2-4_ParSands\6d6D2-4_20250115tip\Batch\6d6D2-4_20250115tip.txt",interim_survey_lines=r"C:\Users\darle\PycharmProjects\Topo_QC_Test\dependencies\SW_PROFILES_PHASE4_ALL\SW_PROFILES_PHASE4_ALL.shp")
#        logging.info("Running the rest of the script...")
#        topo_tool.run_topo_qc()
#    except ImportError as e:
#        logging.error(e)
#    except ValueError as e:
#        logging.error(e)
#    except FileNotFoundError as e:
#        logging.error(e)
#
#if __name__ == '__main__':
#    main()
#
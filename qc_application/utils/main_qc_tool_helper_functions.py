import os
import logging
import re
from datetime import datetime
from typing import Optional
import arcpy
from pathlib import Path
import numpy as np
import pandas as pd
from itertools import chain
from qc_application.utils.database_connection import establish_connection
from sqlalchemy import text

from qc_application.utils.check_photo_helper_functions import *

def is_baseline_survey(input_text_path: str) -> bool:
    """
    Checks if a survey is a baseline survey based on the input file path.

    A survey is considered a baseline if any folder in the path ends with 'tb'
    (e.g., 'C:/Surveys/Project_2024tb/data.txt').

    Args:
        input_text_path (str): The full path to the survey data file.

    Returns:
        bool: True if the path contains a folder ending in 'tb', False otherwise.
    """
    # Normalize the path to handle different OS separators and split into parts.
    parts = os.path.normpath(input_text_path).split(os.sep)

    # Check if any part of the path ends with 'tb' in a case-insensitive manner.
    return any(part.lower().endswith('tb') for part in parts)

def get_region(input_path: str) -> Optional[str]:
    """
    Extracts the region from the input file path.

    The region is identified by checking for specific, predefined region
    names within the path string.

    Args:
        input_path (str): The full path to the survey data file.

    Returns:
        Optional[str]: The extracted region name, or None if no region is found.
    """
    regions = ["TSW_IoS", "TSW_PCO", "TSW01", "TSW02", "TSW03", "TSW04"]

    # Iterate through the list of regions and return the first one found in the path.
    for region in regions:
        if region in input_path:
            logging.info(f"Region set to {region} :)")
            return region

    # If the loop completes, no region was found.
    logging.error(
        f"No region could be extracted from the input text file path. "
        f"Expected one of: {regions}\nPlease check the input file path."
    )
    return None

def extract_survey_unit(input_path: str) -> Optional[str]:
    """
    Extracts the survey unit from the input file path.

    Args:
        input_path (str): The full path to the survey data file.

    Returns:
        Optional[str]: The extracted survey unit or None if the format is incorrect.
    """
    try:
        # Assumes the format is 'XXunit_date.ext'
        filename = os.path.basename(input_path)
        parts = filename.split("_")
        if len(parts) > 1:
            return parts[0][2:]
        return None
    except (IndexError, TypeError):
        return None

def check_survey_unit_in_shapefile(unit: str, shapefile_path: str) -> bool:
    """
    Checks if a given survey unit exists in the 'SURVEY_UNT' column
    of a provided shapefile.

    Args:
        unit (str): The survey unit to check.
        shapefile_path (str): The path to the survey profile lines shapefile.

    Returns:
        bool: True if the unit is found, False otherwise.
    """
    if not arcpy.Exists(shapefile_path):
        logging.error(f"Shapefile not found: {shapefile_path}")
        return False

    try:
        # Use a list comprehension for efficiency and to handle large datasets.
        # This is generally faster than converting to a DataFrame for a simple check.
        with arcpy.da.SearchCursor(shapefile_path, 'SURVEY_UNT') as cursor:
            units = {row[0] for row in cursor}
            return unit in units
    except RuntimeError:
        logging.error("Column 'SURVEY_UNT' not found in shapefile!")
        return False
    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}")
        return False

def get_input_survey_unit(input_path: str, survey_profile_lines_shp: str) -> Optional[str]:
    """
    Extracts the survey unit from the input file path and validates its
    existence in the survey profile lines shapefile.

    Args:
        input_path (str): The full path to the survey data file.
        survey_profile_lines_shp (str): The path to the shapefile to check against.

    Returns:
        Optional[str]: The validated survey unit, or None if it fails to
                       extract or is not found in the shapefile.
    """
    input_survey_unit = extract_survey_unit(input_path)

    if not input_survey_unit:
        logging.warning(
            f"Could not extract survey unit from input path: {input_path}."
        )
        return None

    if check_survey_unit_in_shapefile(input_survey_unit, survey_profile_lines_shp):
        logging.info(f"Extracted Survey Unit Set to {input_survey_unit} :)")
        return input_survey_unit
    else:
        logging.warning(
            f"Extracted Survey Unit '{input_survey_unit}' not found in shapefile at '{survey_profile_lines_shp}'!"
        )
        return None

def make_file_friendly_survey_unit(extracted_survey_unit: str) -> str:
    """
    Returns a formatted survey unit that can be used in file names.

    This function replaces the hyphen (-) in the survey unit string with an
    underscore (_) to make it compatible with file naming conventions.

    Args:
        extracted_survey_unit (str): The survey unit string, e.g., "6d6D1-6".

    Returns:
        str: The formatted survey unit, e.g., "6d6D1_6".
    """
    formatted_survey_unit = extracted_survey_unit.replace("-", "_")
    return formatted_survey_unit

def extract_survey_cell(input_path: str) -> Optional[str]:
    """
    Extracts the survey cell from the input file path.

    The cell is assumed to be the first two characters of the filename.

    Args:
        input_path (str): The full path to the survey data file.

    Returns:
        Optional[str]: The extracted survey cell, or None if the format is incorrect.
    """
    try:
        filename = os.path.basename(input_path)
        # Check if the filename has at least 2 characters before slicing
        if len(filename) >= 2:
            return filename[:2]
        return None
    except (TypeError, IndexError):
        return None

def check_cell_in_shapefile(cell: str, shapefile_path: str) -> bool:
    """
    Checks if a given cell exists in the 'CELL' column of a provided shapefile.

    Args:
        cell (str): The cell string to check.
        shapefile_path (str): The path to the survey profile lines shapefile.

    Returns:
        bool: True if the cell is found, False otherwise.
    """
    if not arcpy.Exists(shapefile_path):
        logging.error(f"Shapefile not found: {shapefile_path}")
        return False
    try:
        # Using a search cursor is more memory-efficient for a simple existence check.
        with arcpy.da.SearchCursor(shapefile_path, 'CELL') as cursor:
            # Create a set for quick lookups
            cells = {row[0] for row in cursor}
            return cell in cells
    except RuntimeError:
        logging.error("Column 'CELL' not found in the supplied survey profile lines shapefile!")
        return False
    except Exception as e:
        logging.error(f"An unexpected error occurred while checking shapefile: {e}")
        return False

def get_survey_cell(input_path: str, survey_profile_lines_shp: str) -> Optional[str]:
    """
    Extracts the survey cell from the input file path and validates its
    existence in the survey profile lines shapefile.

    Args:
        input_path (str): The full path to the survey data file.
        survey_profile_lines_shp (str): The path to the shapefile to check against.

    Returns:
        Optional[str]: The validated survey cell, or None if it fails to
                       extract or is not found in the shapefile.
    """
    extracted_cell = extract_survey_cell(input_path)

    if not extracted_cell:
        logging.warning("Could not extract survey cell from the input file path.")
        return None

    if check_cell_in_shapefile(extracted_cell, survey_profile_lines_shp):
        arcpy.AddMessage(f"Extracted Cell Set to  {extracted_cell} :)")
        return extracted_cell
    else:
        arcpy.AddError(f"Extracted Cell {extracted_cell} was not found in the survey profile lines shapefile!")
        return None

def get_survey_completion_date(input_text: str) -> Optional[str]:
    """
    Extracts the survey completion date from the input text file path using regex.

    The date is expected to be an 8-digit number following an underscore in the filename.

    Args:
        input_text (str): The full path to the input text file.

    Returns:
        Optional[str]: The extracted survey completion date as a string (YYYYMMDD),
                       or None if the date cannot be extracted.
    """
    try:
        filename = os.path.basename(input_text)
        initial_split = filename.split("_")

        if len(initial_split) < 2:
            logging.error("Input file name is incorrectly formatted: expected an underscore.")
            return None

        # The date is assumed to be in the second part of the split filename
        regex_find = re.search(r"\d{8}", initial_split[1])
        if regex_find:
            survey_comp_date = regex_find.group(0)
            arcpy.AddMessage(f"Survey Date Selected: {survey_comp_date}")
            return survey_comp_date
        else:
            logging.error("Input file date is incorrectly formatted: no 8-digit date found.")
            return None

    except Exception:
        # A generic catch-all for any other unexpected errors
        logging.error("An unexpected error occurred while trying to extract the date.")
        return None

def get_qc_workspace(input_path: str) -> Optional[str]:
    """
    Finds and returns the path to the QC_Files folder associated with the input path.

    The function checks if the input path is valid and then searches for a folder
    containing "QC" in the parent directory of the input file.

    Args:
        input_path (str): The full path to the input data file.

    Returns:
        Optional[str]: The absolute path to the QC workspace, or None if it cannot be found.
    """
    input_path_obj = Path(input_path)

    if not input_path_obj.exists():
        logging.warning(
            f"The input file path '{input_path}' is not valid! Please check the path and try again."
        )
        return None

    parent_dir = input_path_obj.parent
    grandparent_dir = parent_dir.parent

    # Find the first folder in the grandparent directory that contains "QC"
    for folder in grandparent_dir.iterdir():
        if folder.is_dir() and "QC" in folder.name:
            qc_workspace = str(folder.resolve())
            logging.info(f"QC file path set to {qc_workspace}")
            return qc_workspace

    logging.warning(f"There is no QC_Files folder in this directory: '{grandparent_dir}', add one to continue.")
    return None

def universal_text_file_converter(input_file_path :str):
    """
    Reads a tab-separated text file, standardizes its headers, and returns a pandas DataFrame.

    Args:
        input_file_path (str): The file path to the input text file.

    Returns:
        pd.DataFrame: A DataFrame with standardized headers if successful, otherwise an empty DataFrame.
    """
    try:
        df = pd.read_csv(input_file_path, delimiter='\t', dtype=str)
    except Exception as e:
        logging.error(f"Error reading the input file: {e}")
        return pd.DataFrame()

    # Standardize column names
    column_rename_map = {
        'Chainage': None,  # Will be dropped
        'Elevation_OD': 'Elevation',
        'Code': 'FC',
        'Feature Code': 'FC',
        'Profile Reg_ID': 'Reg_ID'
    }

    df.rename(columns={k: v for k, v in column_rename_map.items() if v is not None}, inplace=True)

    # Drop the Chainage column if it exists
    if 'Chainage' in df.columns:
        df.drop(columns=['Chainage'], inplace=True)

    # Standardize 'Reg_ID' and add a 'Unique_ID'
    if 'Reg_ID' in df.columns:
        df['Reg_ID'] = '_' + df['Reg_ID'].astype(str)
        df['Unique_ID'] = df.index.astype(str) + df['Reg_ID']

    # Validate headers
    target_headers = ['Easting', 'Northing', 'Elevation', 'FC', 'Reg_ID']
    current_headers = set(df.columns)

    if set(target_headers).issubset(current_headers):
        print("Input text file successfully formatted.")
        return df
    else:
        missing_headers = set(target_headers) - current_headers
        logging.warning(f"Required headers are missing: {missing_headers}. Returning an empty DataFrame.")
        return pd.DataFrame()

def get_mlsw(extracted_survey_unit, extracted_cell, mlsw_dict):
    """
    Returns the MLSW value for a given survey unit.

    Args:
        extracted_survey_unit (str): The extracted survey unit identifier.
        extracted_cell (str): The extracted cell identifier.
        mlsw_dict (dict): A dictionary containing the MLSW values.

    Returns:
        any: The MLSW value if found, otherwise None.
    """
    survey_unit_key = extracted_cell + extracted_survey_unit

    mlsw_value = mlsw_dict.get(survey_unit_key)

    if mlsw_value is None:
        logging.warning(f"MLSW value not found for key: {survey_unit_key}")
    else:
        logging.info(f"MLSW set to {mlsw_value}")

    return mlsw_value

def create_point_file_name(extracted_cell, file_friendly_survey_unit, survey_completion_date):
    """
    Creates a standardized file name for a point feature class.

    Args:
        extracted_cell (str): The cell identifier.
        file_friendly_survey_unit (str): The survey unit identifier, formatted for file names.
        survey_completion_date (str): The completion date of the survey.

    Returns:
        str: A string representing the standardized file name.
    """
    file_name = f"{extracted_cell}{file_friendly_survey_unit}_{survey_completion_date}_tip_Auto.shp"
    return file_name

def make_xy_event_layer(standardised_df, workspace, output_file_name):
    """
    Creates a point feature class (.shp) from a pandas DataFrame.

    This function first saves the DataFrame to a temporary CSV file, as the
    arcpy.management.XYTableToPoint tool cannot directly process a DataFrame.
    It then uses the temporary CSV to create the point feature class.

    Args:
        standardised_df (pd.DataFrame): The input DataFrame containing 'Easting', 'Northing',
                                        and 'Elevation' columns.
        workspace (str): The directory path where the output file will be saved.
        output_file_name (str): The desired name for the output shapefile (e.g., 'points.shp').

    Returns:
        str: The full path to the newly created point feature class.
    """
    # Create the full path for the temporary and output files
    temp_csv_path = os.path.join(workspace, "temp.csv")
    out_feature_class = os.path.join(workspace, output_file_name)

    arcpy.AddMessage(f"Creating XY point layer: {output_file_name}")

    try:
        # Save the DataFrame to a temporary CSV file
        standardised_df.to_csv(temp_csv_path, index=False)

        # Set the local variables for the geoprocessing tool
        in_table = temp_csv_path

        # Check if the output file already exists to prevent an overwrite error
        if not arcpy.Exists(out_feature_class):
            arcpy.management.XYTableToPoint(
                in_table = in_table,
                out_feature_class  =out_feature_class,
                x_field = "Easting",
                y_field = "Northing",
                z_field = "Elevation",
                coordinate_system=arcpy.SpatialReference(27700)
            )
            logging.info(f"Successfully created point feature class: {out_feature_class}")
        else:
            logging.warning(f"Output file already exists, skipping creation: {out_feature_class}")

    except Exception as e:
        logging.error(f"Error creating point feature class: {e}")
        # Re-raise the exception to be handled by the calling function
        raise
    finally:
        # Ensure the temporary CSV file is always removed
        if os.path.exists(temp_csv_path):
            os.remove(temp_csv_path)
            logging.debug(f"Removed temporary file: {temp_csv_path}")

    return out_feature_class

def feature_code_check(standardised_df):
    """
    Compares surveyed feature codes in a DataFrame to a list of acceptable codes.

    Args:
        standardised_df) (pd.DataFrame): The DataFrame containing a column named 'FC'
                          with feature codes to be validated.

    Returns:
        dict: A dictionary where keys are the DataFrame index (row number)
              of invalid feature codes and values are the incorrect codes.
    """
    # A set is much faster for checking membership (O(1) vs O(n) for a list).
    acceptable_codes = {
        "S", "M", "G", "GS", "MS", "B", "R", "SD", "SM", "W", "GM", "GR", "D", "DV",
        "F", "X", "FB", "CT", "CE", "CF", "SH", "ZZ", "HW",
        "s", "m", "g", "gs", "ms", "b", "r", "sd", "sm", "w", "gm", "gr", "d", "dv",
        "f", "x", "fb", "ct", "ce", "cf", "sh", "zz", "hw"
    }

    # Find rows where the 'FC' value is not in the set of acceptable codes.
    # This is more efficient and "vectorized" than a manual loop.
    invalid_codes_df = standardised_df[~standardised_df['FC'].isin(acceptable_codes)]

    # Create the dictionary from the filtered DataFrame.
    bad_feature_code_dict = dict(zip(invalid_codes_df.index, invalid_codes_df['FC']))

    # convert to DataFrame for report generation
    bad_feature_code_df = pd.DataFrame(
        list(bad_feature_code_dict.items()),
        columns=['Index', 'FC']
    )

    # Log the results
    if bad_feature_code_dict:
        logging.warning(f"Found {len(bad_feature_code_dict)} invalid feature codes at rows: {bad_feature_code_dict}")
    else:
        logging.info("All feature codes correctly defined. ✅")

    return bad_feature_code_df

def extract_interim_lines(survey_profile_lines_shp,workspace,extracted_cell,file_friendly_survey_unit,is_baseline_survey = False
    ):
    """
    Selects a subset of lines from a shapefile based on a survey unit and type,
    then saves the selection to a new shapefile.

    Args:
        survey_profile_lines_shp (str): Path to the input shapefile of profile lines.
        workspace (str): The directory where the output shapefile will be saved.
        extracted_cell (str): The cell identifier for the survey.
        file_friendly_survey_unit (str): The survey unit identifier formatted for a file name.
        is_baseline_survey (bool, optional): If True, queries for baseline lines;
                                           otherwise, queries for interim lines. Defaults to False.

    Returns:
        str: The full path to the newly created output shapefile.
    """
    try:
        # Construct the output path using os.path.join for platform compatibility
        output_shp = os.path.join(
            workspace,
            f"SelectedInterimLines_{extracted_cell}{file_friendly_survey_unit}_Auto.shp"
        )

        # Construct a clean WHERE clause using an f-string
        query_friendly_survey_unit = file_friendly_survey_unit.replace("_", "-")
        query_type = "BASELINE" if is_baseline_survey else "INTERIM"
        where_clause = f"SURVEY_UNT = '{query_friendly_survey_unit}' AND {query_type} = 'YES'"

        logging.info(f"Using query: {where_clause}")

        # Run the geoprocessing tool to select and save the features
        arcpy.Select_analysis(survey_profile_lines_shp, output_shp, where_clause)

        logging.info(f"Selected lines saved to: {output_shp}")

        return output_shp

    except arcpy.ExecuteError:
        logging.error("ArcPy geoprocessing error:")
        logging.error(arcpy.GetMessages(2))
        return None
    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}")
        return None

def create_offline_buffer_file_name(region, workspace, extracted_cell, file_friendly_survey_unit):
    """
    Creates a standardized file path for an offline buffer shapefile based on a region's tolerance.

    Args:
        region (str): The region identifier (e.g., 'TSW_IoS').
        workspace (str): The directory where the output file will be saved.
        extracted_cell (str): The cell identifier.
        file_friendly_survey_unit (str): The survey unit identifier, formatted for a file name.

    Returns:
        str: The full path to the output shapefile.
    """
    # Define a dictionary for region-specific tolerances
    tolerance_map = {
        ("TSW_IoS", "TSW_PCO"): 0.03
    }

    # Check if the region is in the keys of the tolerance map.
    # The .get() method returns a default value if the key isn't found.
    tolerance = tolerance_map.get(tuple(sorted([region]))) or 0.1

    # Log the tolerance value
    logging.info(f"Offline tolerance set to {tolerance}m")

    # Construct the file name using a clean f-string
    file_name = f"Buffer_{str(tolerance).replace('.', '')}m_{extracted_cell}{file_friendly_survey_unit}_Auto.shp"

    # Use os.path.join for robust path creation
    file_path = os.path.join(workspace, file_name)

    return file_path

def create_offline_buffer(region, offline_line_buffer_path, selected_interim_lines):
    """
    Creates a buffer on selected profile lines with a region-specific tolerance.

    Args:
        region (str): The region identifier (e.g., 'TSW_IoS').
        offline_line_buffer_path (str): The full path for the output buffer shapefile.
        selected_interim_lines (str): The full path to the input line feature class.
    """
    # Determine the buffer distance based on the region.
    # A dictionary is used to handle the specific cases, with a default value.
    buffer_distances = {
        "TSW_IoS": 0.03,
        "TSW_PCO": 0.03
    }

    buffer_distance = buffer_distances.get(region, 0.1)

    # Run the buffer analysis with the determined distance.
    # arcpy.env.overwriteOutput = True handles the overwrite, so no pre-check is needed.
    arcpy.Buffer_analysis(
        in_features=selected_interim_lines,
        out_feature_class=offline_line_buffer_path,
        buffer_distance_or_field=buffer_distance
    )

    logging.info(f"Offline Buffer of {buffer_distance}m created at: {offline_line_buffer_path}")

def generate_offline_points_path(workspace, extracted_cell, file_friendly_survey_unit):
    """
    Generates a standardized file path for an offline points shapefile.

    Args:
        workspace (str): The directory where the output file will be saved.
        extracted_cell (str): The cell identifier.
        file_friendly_survey_unit (str): The survey unit identifier, formatted for a file name.

    Returns:
        str: The full path to the output shapefile.
    """
    file_name = f"Offline_points_{extracted_cell}{file_friendly_survey_unit}_Auto.shp"

    # Use os.path.join for robust path creation
    file_path = os.path.join(workspace, file_name)

    return file_path

def get_offline_points(points_file_path, offline_line_buffer_path, standardised_df,
                     offline_points_path, workspace):
    """
    Identifies points lying outside a buffer polygon and saves them to a new shapefile.

    The function works by:
    1. Clipping all survey points to the buffer to find 'inline' points.
    2. Using pandas to efficiently identify points from the original dataset that are NOT in the clipped set.
    3. Saving these 'offline' points to a new shapefile for further analysis.

    Args:
        points_file_path (str): Path to the input shapefile of all survey points.
        offline_line_buffer_path (str): Path to the buffer polygon shapefile.
        standardised_df (pd.DataFrame): DataFrame containing all survey point data and Unique_ID.
        offline_points_path (str): Path for the output shapefile of offline points.
        workspace (str): The directory for temporary files.

    Returns:
        pd.DataFrame: A DataFrame containing the data for all identified offline points.
    """
    # Create robust paths for temporary files
    clip_points_path = os.path.join(workspace, "clipped_points.shp")
    offline_points_csv_path = os.path.join(workspace, "offline_points.csv")

    try:
        arcpy.AddMessage("Identifying offline points...")



        # 1. Clip survey points using the offline buffer to get "inline" points
        arcpy.analysis.Clip(points_file_path, offline_line_buffer_path, clip_points_path)

        # 2. Get the unique IDs of the clipped points
        inline_points_ids_set = set(
            p[0] for p in arcpy.da.SearchCursor(clip_points_path, "Unique_ID")
        )

        # 3. Use pandas to efficiently find points that are NOT in the clipped set
        offline_mask = ~standardised_df["Unique_ID"].isin(inline_points_ids_set)
        offline_points_df = standardised_df[offline_mask]

        if not offline_points_df.empty:
            # 4. If offline points exist, save them to a shapefile
            arcpy.AddWarning(f"{len(offline_points_df)} offline points were found.")

            # Save filtered DataFrame to a temporary CSV
            offline_points_df.to_csv(offline_points_csv_path, index=False)

            # Create the output shapefile from the temporary CSV
            arcpy.management.XYTableToPoint(
                in_table=offline_points_csv_path,
                out_feature_class=offline_points_path,
                x_field="Easting",
                y_field="Northing",
                z_field="Elevation",
                coordinate_system=arcpy.SpatialReference(27700)
            )

        else:
            arcpy.AddMessage("No offline points were found. ✅")

    except arcpy.ExecuteError:
        logging.error("ArcPy geoprocessing error.")
        logging.error(arcpy.GetMessages(2))
        raise
    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}")
        raise
    finally:
        # 5. Clean up temporary files, ensuring they are deleted even if an error occurs
        if arcpy.Exists(clip_points_path):
            arcpy.Delete_management(clip_points_path)
        if os.path.exists(offline_points_csv_path):
            os.remove(offline_points_csv_path)

    return offline_points_df

def generate_buffer_output_path(workspace, extracted_cell, file_friendly_survey_unit):
    """
    Generates a standardized file path for a spacing buffer shapefile.

    Args:
        workspace (str): The directory where the output file will be saved.
        extracted_cell (str): The cell identifier.
        file_friendly_survey_unit (str): The survey unit identifier, formatted for a file name.

    Returns:
        str: The full path to the output shapefile.
    """
    file_name = f"Spacing_Buffer_{extracted_cell}{file_friendly_survey_unit}_Auto.shp"

    # Use os.path.join for robust path creation
    file_path = os.path.join(workspace, file_name)

    return file_path

def create_distance_buffer(points_file_path, buffer_file_path, spacing_unit_error):
    """
    Generates a buffer around each surveyed point for a visual spacing check.

    Args:
        points_file_path (str): The full path to the input survey points feature class.
        buffer_file_path (str): The full path for the output buffer shapefile.
        spacing_unit_error (float): The distance in meters for the buffer.
    """
    # Run the buffer analysis with the specified distance.
    # arcpy.env.overwriteOutput = True handles overwriting.
    arcpy.analysis.Buffer(
        in_features=points_file_path,
        out_feature_class=buffer_file_path,
        buffer_distance_or_field=spacing_unit_error
    )

    logging.info(f"Spacing buffer created at: {buffer_file_path}")

# --TODO this is untested.
def spacing_check(df, spacing_unit_error):
    """
    Checks the distance between consecutive points within each unique profile
    and identifies any distances that exceed a specified tolerance.

    Args:
        df (pd.DataFrame): DataFrame containing point data with 'Easting',
                          'Northing', and 'Reg_ID' columns.
        spacing_unit_error (float): The maximum allowed distance between points.

    Returns:
        pd.DataFrame: A DataFrame where the index is the profile name and
                      the values are the distances that are over the specified tolerance.
    """
    logging.info("Running Spacing Checks:")

    # Ensure numeric dtype (non-numeric values become NaN)
    df['Easting'] = pd.to_numeric(df['Easting'], errors='coerce')
    df['Northing'] = pd.to_numeric(df['Northing'], errors='coerce')

    over_spacing_dict = {}

    for profile_name, group in df.groupby("Reg_ID"):

        # Drop rows with missing coords to avoid NaN propagation
        group = group.dropna(subset=['Easting', 'Northing'])

        if len(group) < 2:
            continue  # can't compute spacing with fewer than 2 points

        easting_diff = group['Easting'].diff().iloc[1:]
        northing_diff = group['Northing'].diff().iloc[1:]

        distances = np.sqrt(easting_diff ** 2 + northing_diff ** 2)

        values_over_spec = distances[distances > spacing_unit_error]

        if not values_over_spec.empty:
            over_spacing_dict[profile_name] = values_over_spec.tolist()

    over_spacing_df = pd.DataFrame.from_dict(over_spacing_dict, orient='index')

    if not over_spacing_df.empty:
        logging.warning(f"One or more profiles have spacing over {spacing_unit_error}m :(\n{over_spacing_df}")
    else:
        logging.info(f"All profiles have spacing within {spacing_unit_error}m. ✅")

    return over_spacing_df

# --TODO this is untested.
def check_made_depth(df, mlsw_value):
    """
    Checks if the lowest elevation for each profile is at or below the
    specified MLSW (Mean Low Water Springs) value.

    Args:
        df (pd.DataFrame): The DataFrame containing point data with 'Elevation'
                          and 'Reg_ID' columns.
        mlsw_value (float): The Mean Low Water Springs value to compare against.

    Returns:
        pd.DataFrame: A DataFrame containing data for all profiles that failed
                      to make depth. Returns an empty DataFrame if all profiles
                      made depth.
    """
    if df.empty:
        logging.warning("Input DataFrame is empty. Cannot perform depth check.")
        return pd.DataFrame()

    logging.info("Running Made Depth Checks:")

    # Ensure Elevation is a float for accurate comparison
    df["Elevation"] = pd.to_numeric(df["Elevation"], errors='coerce')

    # Ensure MLSW is numeric
    mlsw_value = pd.to_numeric(mlsw_value, errors='coerce')

    # Get the lowest elevation for each profile using a single groupby operation
    profiles_lowest_elevations = df.groupby('Reg_ID')['Elevation'].min().reset_index()

    # Use vectorized operations to calculate new columns
    profiles_lowest_elevations["MLSW"] = mlsw_value
    profiles_lowest_elevations["Difference"] = profiles_lowest_elevations["Elevation"] - mlsw_value
    profiles_lowest_elevations["Made_Depth"] = profiles_lowest_elevations["Elevation"] <= mlsw_value

    # Filter for profiles that did not make depth
    failed_depth_profiles = profiles_lowest_elevations[profiles_lowest_elevations["Made_Depth"] == False]

    # Log the results
    if not failed_depth_profiles.empty:
        logging.warning(
            f"One or more survey lines failed to make depth :(\n{failed_depth_profiles}")
    else:
        logging.info(f"All survey lines made depth. ✅\n{profiles_lowest_elevations}")

    return failed_depth_profiles

def check_metadata(input_text):
    """
    Checks a directory for the presence of a file containing "Meta" in its name.

    Args:
        directory_path (str): The path to the directory to be checked.

    Returns:
        str: "Pass" if a metadata file is found, otherwise "Issue".
    """


    directory_path = Path(input_text).parent

    try:
        # Check if the directory exists and is not empty
        if not os.path.isdir(directory_path) or not os.listdir(directory_path):
            logging.warning(f"Directory not found or is empty: {directory_path}")
            return "Issue"

        # Use a list comprehension with 'any' for an efficient check
        if any("Meta" in file for file in os.listdir(directory_path)):
            logging.info(f"Metadata file found in directory: {directory_path}")
            return "Pass"
        else:
            logging.info(f"No metadata file found in directory: {directory_path}")
            return "Issue"

    except Exception as e:
        logging.error(f"An error occurred while checking metadata: {e}")
        return "Issue"

def check_survey_report(input_text):
    """
    Checks a directory for the presence of a file containing "Report" in its name.

    Args:
        directory_path (str): The path to the directory to be checked.

    Returns:
        tuple: A tuple containing two strings:
               - The first string is "Pass" if a report is found, otherwise "Issue".
               - The second string is "Auto Checked" if a report is found, otherwise "Missing".
    """

    directory_path = Path(input_text).parent


    try:
        if not os.path.isdir(directory_path) or not os.listdir(directory_path):
            logging.warning(f"Directory not found or is empty: {directory_path}")
            return "Issue", "Missing"

        if any("Report" in file for file in os.listdir(directory_path)):
            logging.info(f"Survey report found in directory: {directory_path}")
            return "Pass", "Auto Checked"
        else:
            logging.info(f"No survey report found in directory: {directory_path}")
            return "Issue", "Missing"

    except Exception as e:
        logging.error(f"An error occurred while checking for a survey report: {e}")
        return "Issue", "Missing"

def get_overspacing_status(lengths_over_spec):
    """
    Determines the status of spacing based on a list of over-spec lengths.

    Args:
        lengths_over_spec (list, pd.DataFrame): A list or DataFrame containing
                                                any spacing values that exceed the tolerance.

    Returns:
        str: "Issue" if the list is not empty, otherwise "Pass".
    """
    if len(lengths_over_spec) > 0:
        return "Issue"
    else:
        return "Pass"

def get_made_depth_status(depth_checks_df):
    """
    Determines the status of the "made depth" check based on the input DataFrame.

    Args:
        depth_checks_df (pd.DataFrame): A DataFrame containing profiles that failed the depth check.

    Returns:
        str: "Issue" if the DataFrame is not empty, otherwise "Pass".
    """
    return "Issue" if not depth_checks_df.empty else "Pass"

def get_offline_points_status(offline_points_df):
    """
    Determines the status of the "offline points" check based on the input DataFrame.

    Args:
        offline_points_df (pd.DataFrame): A DataFrame containing identified offline points.

    Returns:
        str: "Issue" if the DataFrame is not empty, otherwise "Pass".
    """
    return "Issue" if not offline_points_df.empty else "Pass"

def define_survey_type(survey_completion_date_str, is_baseline_survey):
    """
    Defines the type of a survey based on its completion date and a baseline flag.

    Args:
        survey_completion_date_str (str): The survey completion date in 'YYYYMMDD' format.
        is_baseline_survey (bool): A flag indicating if the survey is a baseline survey.

    Returns:
        str: The defined survey type, such as "Baseline", "Autumn Interim", or "Spring Interim".
    """
    if is_baseline_survey:
        logging.info("Survey type defined as 'Baseline'.")
        return "Baseline"

    try:
        # Convert the string date to a datetime object
        survey_date = datetime.strptime(survey_completion_date_str, "%Y%m%d")
        month = survey_date.month

        # Define the survey type based on the month
        if month in [9, 10, 11, 12]:
            survey_type = "Autumn Interim"
        elif month in [1, 2, 3]:
            survey_type = "Spring Interim"
        else:
            # Handle months that are not explicitly autumn or spring
            logging.warning(
                f"Month {month} does not fit the typical interim survey seasons. Defaulting to 'Spring Interim'."
            )
            survey_type = "Spring Interim"

        logging.info(f"Survey type defined as '{survey_type}'.")
        return survey_type

    except ValueError:
        logging.error(f"Invalid date format for '{survey_completion_date_str}'. Expected 'YYYYMMDD'.")
        return "Unknown"
    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}")
        return "Unknown"

def extract_survey_meta(input_text, extracted_survey_unit, survey_completion_date,
                        survey_type, extracted_cell, bool_baseline_survey,
                        lengths_over_spec, depth_checks, offline_points, set_workspace,
                        data_profile_xyz_c):
    """
    Extracts survey metadata from the input text file path and returns a dictionary.

    Args:
        input_text (str): Path to the input text file.
        extracted_survey_unit (str): The extracted survey unit.
        survey_completion_date (str): The survey completion date.
        survey_type (str): The type of survey (e.g., "Baseline", "Interim").
        extracted_cell (str): The extracted cell identifier.
        bool_baseline_survey (bool): Flag indicating if the survey is a baseline survey.
        lengths_over_spec (pd.DataFrame): DataFrame of profiles with over-spec spacing values.
        depth_checks (pd.DataFrame): DataFrame of profiles that failed depth checks.
        offline_points (pd.DataFrame): DataFrame of points found offline.
        set_workspace (str): The path to the QC folder.
        data_profile_xyz_c (str): Check status of the data profile file.

    Returns:
        dict: A dictionary containing the extracted and generated metadata.
    """
    gen_date_checked = datetime.now().strftime("%Y-%m-%d")
    gen_name = "Auto"

    # Define the common metadata dictionary
    survey_meta = {
        "survey_unit": extracted_cell + extracted_survey_unit,
        "survey_type": survey_type,
        "completion_date": survey_completion_date,
        "survey_received": survey_completion_date,
        "delivery_reference": "Where I get this",
        "gen_metadata": check_metadata(input_text),
        "gen_metadata_c": "Auto Checked" if check_metadata(input_text) == "Pass" else "Missing",
        "gen_survey_report": check_survey_report(input_text)[0],
        "gen_survey_report_c": check_survey_report(input_text)[1],
        "gen_date_checked": gen_date_checked,
        "gen_name": gen_name,
        "data_profile_xyz_txt": os.path.basename(input_text),
        "data_profile_xyz_txt_c": data_profile_xyz_c,
        "checks_pl_point_spacing": get_overspacing_status(lengths_over_spec),
        "checks_pl_point_spacing_c": f"{len(lengths_over_spec)} over spacing found",
        "checks_pl_seaward_limit": get_made_depth_status(depth_checks),
        "checks_pl_seaward_limit_c": f"{len(depth_checks)} profiles failed to make depth",
        "checks_pl_offline_variation": get_offline_points_status(offline_points),
        "checks_pl_offline_variation_c": f"{len(offline_points)} found offline",
        "qc_folder": set_workspace,
    }

    # The `if` condition is no longer needed since the dictionary is the same for both cases.
    # The `bool_baseline_survey` variable is already used to set the `survey_type` parameter
    # before it is passed to this function.

    logging.info(f"Survey Metadata: {survey_meta}")
    return survey_meta

def find_other_folder(input_text_path: str) -> str | None:
    """
    Finds the 'Other' subfolder located two levels up from a given text file path.

    Args:
        input_text_path (str): The full path to the input text file.

    Returns:
        str | None: The full path to the 'Other' folder if it exists, otherwise None.
    """
    try:
        # Go up two directories from the file path to find the parent of the parent folder
        other_dir = Path(input_text_path).parent.parent / "Other"

        if other_dir.is_dir():
            logging.info(f"Found 'Other' folder at: {other_dir}")
            return str(other_dir)
        else:
            logging.error(f"No 'Other' folder could be found at the expected location: {other_dir}")
            return None
    except Exception as e:
        logging.error(f"An error occurred while finding the 'Other' folder: {e}")
        return None

def find_tb_file(other_folder: str) -> Optional[str]:
    """
    Searches for a single file ending with 'tb.txt' in a specified folder.

    Args:
        other_folder (str): The path to the directory to search.

    Returns:
        Optional[str]: The full path to the found file if exactly one is matched,
                       otherwise None.
    """
    try:
        if not os.path.isdir(other_folder):
            logging.error(f"Directory not found: {other_folder}")
            return None

        # Regex to find files ending with 'tb.txt' (case-sensitive)
        pattern = re.compile(r".*tb\.txt$")

        files_in_other = os.listdir(other_folder)
        matching_files = [f for f in files_in_other if pattern.match(f)]

        if len(matching_files) == 1:
            logging.info(f"Successfully found 'tb.txt' file: {matching_files[0]}")
            full_path = os.path.join(other_folder, matching_files[0])
            return full_path
        else:
            logging.warning(
                f"Found {len(matching_files)} matching files for pattern 'tb.txt', expected exactly 1."
            )
            return None
    except Exception as e:
        logging.error(f"An error occurred while searching for the 'tb.txt' file: {e}")
        return None

def find_raster_asc_file(other_folder: str) -> Optional[str]:
    """
    Searches for a single file ending with 'tb.asc' in a specified folder.

    Args:
        other_folder (str): The path to the directory to search.

    Returns:
        Optional[str]: The full path to the found file if exactly one is matched,
                       otherwise None.
    """
    try:
        if not os.path.isdir(other_folder):
            logging.error(f"Directory not found: {other_folder}")
            return None

        # Regex to find files ending with 'tb.asc' (case-insensitive)
        pattern = re.compile(r".*tb\.asc$", re.IGNORECASE)

        files_in_other = os.listdir(other_folder)
        matching_files = [f for f in files_in_other if pattern.match(f)]

        if len(matching_files) == 1:
            logging.info(f"Successfully found raster .asc file: {matching_files[0]}")
            full_path = os.path.join(other_folder, matching_files[0])
            return full_path
        else:
            logging.warning(
                f"Found {len(matching_files)} matching .asc files, expected exactly 1."
            )
            return None
    except Exception as e:
        logging.error(f"An error occurred while searching for the .asc file: {e}")
        return None

def check_photos(survey_profiles: Set[str],survey_completion_date: str,input_text_path: str) -> Dict[str, object]:
    """
    High-level function to check photos for a survey.

    Args:
        survey_profiles: Set of valid survey profile names
        survey_completion_date: Expected completion date as string (YYYYMMDD)
        input_text_path: Path to the survey input text file

    Returns:
        Dictionary of photo check results with any issues found
    """
    photo_check_results: Dict[str, object] = {}

    # Find photos
    found_photos = find_photos(input_text_path)
    if not found_photos:
        logger.warning("No photos found in the directory.")
        return photo_check_results

    logger.info(f"Found photos: {list(found_photos.values())}")

    # Check photo dates
    no_date, incorrect_dates = check_photo_dates(
        photo_dict=found_photos, survey_completion_date=survey_completion_date
    )

    if no_date:
        photo_check_results["Photos_Missing_Date"] = "Photos missing date in filename"
    if incorrect_dates:
        photo_check_results["Photos_Incorrect_Date"] = "Photos incorrect date in filename"

    # If there are issues with dates, skip profile checks
    if photo_check_results:
        logger.info("Photo date issues found, skipping profile checks.")
        return photo_check_results

    # Check photo profiles
    photo_profile_check = check_photo_profiles(found_photos, survey_profiles)
    if photo_profile_check:
        photo_check_results["Photo_Profile_Check"] = photo_profile_check

    return photo_check_results

def run_photo_checks(selected_interim_lines, survey_completion_date, input_text_file,
                     is_baseline_survey, survey_meta):
    """
    Checks for profile photos associated with a survey and updates a metadata dictionary.

    The function identifies unique profiles from the input lines, checks for corresponding
    photos, and then updates the provided survey metadata dictionary with the check results.

    Args:
        selected_interim_lines (str): Path to the feature class containing survey lines.
        survey_completion_date (str): The survey completion date string.
        input_text_file (str): Path to the main input text file.
        is_baseline_survey (bool): A flag for a baseline survey.
        survey_meta (dict): The dictionary to be updated with photo check results.

    Returns:
        dict: The updated survey_meta dictionary.
    """
    logging.info("Checking for photos in the Photography folder...")

    profile_field = "REGIONAL_N"
    unique_profiles = set()

    with arcpy.da.SearchCursor(selected_interim_lines, [profile_field]) as cursor:
        for row in cursor:
            if row[0] is not None:
                unique_profiles.add(row[0].replace("_", ""))

    logging.info(f"Unique profiles found: {unique_profiles}")

    # Assuming check_photos is a separate, well-defined function
    photo_checks = check_photos(
        survey_profiles=list(unique_profiles),
        survey_completion_date=survey_completion_date,
        input_text_path=input_text_file
    )

    # Use conditional variables to eliminate redundant if/else blocks
    if is_baseline_survey:
        photo_status_key = "bl_profile_photos"
        photo_comments_key = "bl_profile_photos_c"
    else:
        photo_status_key = "checks_pl_photos"
        photo_comments_key = "checks_pl_photos_c"

    # Set initial values assuming no issues
    photo_status = "Pass"
    photo_comments = "Auto Checked"

    if photo_checks is None:
        photo_status = "Issue"
        photo_comments = "No photos folder or photos found."
        logging.warning(photo_comments)
    elif len(photo_checks) > 0:
        # Flatten the list of all issues into a single string
        all_issues_flat = list(chain.from_iterable(photo_checks.values()))
        all_issues_str = ", ".join(all_issues_flat)

        photo_status = "Issue"
        photo_comments = all_issues_str
        logging.warning(f"Issues found with profile photos: {photo_comments}")
    else:
        logging.info("No issues found with profile photos. ✅")

    # Update the dictionary in a single, clean step
    survey_meta.update({
        photo_status_key: photo_status,
        photo_comments_key: photo_comments
    })

    logging.info("Checking for photos completed.")
    return survey_meta

# -- Baseline Checks Only --

def find_photography_folder(other_folder: str) -> bool:
    """
    Checks if a 'Photography' folder exists within a given directory and if it contains any files.

    Args:
        other_folder (str): The path to the parent directory.

    Returns:
        bool: True if a non-empty 'Photography' folder is found (case-insensitive),
              otherwise False.
    """
    try:
        # Check for 'Photography' folder in a case-insensitive way
        photography_folder_path = None
        for entry in os.listdir(other_folder):
            if entry.lower() == "photography" and os.path.isdir(os.path.join(other_folder, entry)):
                photography_folder_path = os.path.join(other_folder, entry)
                break

        if photography_folder_path is None:
            logging.warning("No 'Photography' folder found.")
            return False

        # Check if the folder contains any files
        contents = os.listdir(photography_folder_path)

        # A simple check for a non-empty list of contents is enough
        if len(contents) > 0:
            logging.info(f"The 'Photography' folder has {len(contents)} item(s).")
            return True
        else:
            logging.warning("'Photography' folder found but is empty.")
            return False

    except FileNotFoundError:
        logging.error(f"The specified directory does not exist: {other_folder}")
        return False
    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}")
        return False

def create_xy_point_layer(workspace: str, tb_text_file: str) -> Optional[str]:
    """
    Creates an XY point layer from a text file with Easting, Northing, and Z fields.

    The function iterates through a predefined list of possible Z (elevation) field names,
    attempting to create the point feature class for each. It returns the path to the
    first successfully created feature class.

    Args:
        workspace (str): The path to the output geodatabase or folder.
        tb_text_file (str): The full path to the input text file.

    Returns:
        Optional[str]: The full path to the created feature class, or None if creation fails.
    """
    arcpy.env.overwriteOutput = True
    logging.info(f"Attempting to create XY point layer from: {tb_text_file}")

    file_name = os.path.basename(tb_text_file).replace(".txt", "")
    possible_z_fields = ["Elevation_OD", "Elevation", "elevation", "elevation_od"]

    for z_field in possible_z_fields:
        out_feature_class = os.path.join(workspace, f"{file_name}_QC_Auto_{z_field}.shp")
        logging.info(f"Trying Z field: '{z_field}'")

        try:
            arcpy.management.XYTableToPoint(
                in_table=tb_text_file,
                out_feature_class=out_feature_class,
                x_field="Easting",
                y_field="Northing",
                z_field=z_field,
                spatial_reference=arcpy.SpatialReference(27700) # OSGB 1936 British National Grid
            )
            logging.info(f"Successfully created XY Point Layer with Z field '{z_field}': {out_feature_class}")
            return out_feature_class

        except arcpy.ExecuteError as e:
            logging.warning(f"Attempt with Z field '{z_field}' failed due to an ArcPy error: {e}")
        except Exception as e:
            logging.error(f"An unexpected error occurred: {e}")

    logging.error("Failed to create XY Point Layer with any Z field. Exiting.")
    return None

def natural_neighbour_interpolation(workspace: str, xy_point_feature_path: str) -> Optional[str]:
    """
    Performs Natural Neighbour interpolation to create a raster from point data.

    The function attempts to create a raster using several possible Z (elevation) fields
    from the input point feature class.

    Args:
        workspace (str): The path to the output geodatabase or folder.
        xy_point_feature_path (str): The full path to the input point feature class.

    Returns:
        Optional[str]: The full path to the created raster if successful, or None otherwise.
    """
    arcpy.env.overwriteOutput = True
    logging.info(f"Attempting Natural Neighbour interpolation for: {xy_point_feature_path}")

    possible_z_fields = ["Elevation_OD", "Elevation", "elevation", "elevation_od"]

    for z_field in possible_z_fields:
        ras_outpath = os.path.join(workspace, f"ras_1_{z_field}.tif")
        logging.info(f"Trying Z field: '{z_field}'")

        try:
            arcpy.NaturalNeighbor_3d(
                in_point_features=xy_point_feature_path,
                z_field=z_field,
                out_raster=ras_outpath,
                cell_size=1
            )
            logging.info(f"Natural Neighbour Raster created successfully with Z field '{z_field}'.")
            return ras_outpath

        except arcpy.ExecuteError as e:
            logging.warning(f"Attempt with Z field '{z_field}' failed due to an ArcPy error: {e}")
        except Exception as e:
            logging.error(f"An unexpected error occurred: {e}")

    logging.error(
        f"Could not create Natural Neighbour raster for {xy_point_feature_path} with any Z field. Exiting."
    )
    return None

def aggregate_points_for_extent(workspace: str, tb_text_file: str) -> Optional[str]:
    """
    Aggregates points from a text file to create a polygon representing the data extent.

    The function uses the Aggregate Points tool to create a polygon feature class,
    which is useful for defining a data extent for subsequent geoprocessing steps.

    Args:
        workspace (str): The path to the output geodatabase or folder.
        tb_text_file (str): The full path to the input text file with point data.

    Returns:
        Optional[str]: The full path to the created extent feature class, or None otherwise.
    """
    arcpy.env.overwriteOutput = True
    extent_path = os.path.join(workspace, "Ras_Extent.shp")
    logging.info(f"Attempting to create aggregated extent polygon at: {extent_path}")

    try:
        aggregation_distance = 30  # Meters, based on a reasonable project-specific value

        # Use named parameters for clarity
        arcpy.cartography.AggregatePoints(
            in_features=tb_text_file,
            out_feature_class=extent_path,
            aggregation_distance=f"{aggregation_distance} Meters"  # Ensure units are specified
        )

        logging.info(f"Successfully created aggregated extent layer: {extent_path}")
        return extent_path

    except arcpy.ExecuteError as e:
        logging.error(f"ArcPy execution error during AggregatePoints: {e}")
        return None
    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}")
        return None


def extract_by_mask(workspace: str, ras1_path: str, extent_path: str) -> Optional[str]:
    """
    Extracts a raster by a polygon mask to clip it to a specific extent.

    The function uses the 'Extract by Mask' tool to clip the input raster to the
    defined extent of the aggregated points, ensuring the final raster is
    only within the project's area of interest.

    Args:
        workspace (str): The path to the output geodatabase or folder.
        ras1_path (str): The full path to the input raster.
        extent_path (str): The full path to the polygon feature class to use as the mask.

    Returns:
        Optional[str]: The full path to the created clipped raster if successful,
                       otherwise None.
    """
    arcpy.env.overwriteOutput = True
    out_raster = os.path.join(workspace, "ras_1_clipped.tif")
    logging.info(f"Attempting to clip raster {ras1_path} to extent {extent_path}.")

    try:
        # Use named parameters for clarity and specify 'ExtractByMask' for clarity
        arcpy.sa.ExtractByMask(
            in_raster=ras1_path,
            in_mask_data=extent_path
        )

        logging.info(f"Successfully clipped raster to extent. Output: {out_raster}")
        return out_raster

    except arcpy.ExecuteError as e:
        logging.error(f"ArcPy execution error during Extract by Mask: {e}")
        return None
    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}")
        return None


def create_os_tiles(tb_text_file):
    """
    Create OS-Tiles from TB.txt and Raster ASC files using the SplitOSTiles class.

    Args:
        tb_text_file (str): Path to the TB.txt file.

    Returns:
        dict: A dictionary with the status of OS-Tile creation:
            {
                "checks_cd_ascii_created_split": "Pass" or "Issue",
                "checks_cd_ascii_created_split_c": "Auto Generated" or "Auto Generation Failed"
            }
    """
    status = {
        "checks_cd_ascii_created_split": "Issue",
        "checks_cd_ascii_created_split_c": "Auto Generation Failed"
    }

    try:

        from qc_application.services.topo_splitting_os_tiles_service import SplitOSTiles

        grandparent_dir = os.path.dirname(os.path.dirname(tb_text_file))

        split_tile = SplitOSTiles(
            tb_folder_path=grandparent_dir,
            ostile_path=r"dependencies/OS_Tiles_All/OSTiles_Merged.shp"
        )
        split_tile.get_os_tile_names()
        split_tile.split_ascii_into_rasters()
        split_tile.convert_rasters_to_ascii()
        split_tile.clean_up_files()

        logging.info("OS_Tiles created successfully")
        status.update({
            "checks_cd_ascii_created_split": "Pass",
            "checks_cd_ascii_created_split_c": "Auto Generated"
        })

    except Exception as e:
        logging.error(f"Error creating OS_Tiles: {e}")

    return status


def run_baseline_checks(input_text_file, workspace, survey_meta, bool_baseline_survey):
    """
    Perform baseline data checks for a survey and run downstream geoprocessing.

    Args:
        input_text_file (str): Path to the input text file for baseline survey.
        workspace (str): Path to the workspace for geoprocessing outputs.
        survey_meta (dict): Dictionary to update with check results.
        bool_baseline_survey (bool): Whether a baseline survey exists.

    Returns:
        tuple: Paths of generated layers in the following order:
            (xy_point_layer_path, ras1_path, aggregate_points_path, mask_path)
            Returns (None, None, None, None) if checks fail.
    """
    if not bool_baseline_survey:
        return None, None, None, None

    # Initialize survey_meta with default failure states
    survey_meta.update({
        "bl_other_data": "Issue",
        "bl_other_data_c": "Missing, could not be found",
        "data_baseline_xyz_txt": "Issue",
        "data_baseline_xyz_txt_c": "Missing, could not be found",
        "data_raster_grid": "Issue",
        "data_raster_grid_c": "Found",
        "bl_profile_photos": "Issue",
        "bl_profile_photos_c": "Missing, could not be found",
        "checks_cd_ascii_created_split": "false",
    })

    # Locate the 'other' folder
    other_folder = find_other_folder(input_text_path=input_text_file)
    if not other_folder:
        return None, None, None, None

    # File checks
    tb_text_file = find_tb_file(other_folder)
    raster_asc_file = find_raster_asc_file(other_folder)
    has_photos = find_photography_folder(other_folder)

    if tb_text_file:
        survey_meta.update({
            "data_baseline_xyz_txt": os.path.basename(tb_text_file),
            "data_baseline_xyz_txt_c": "Found"
        })

    if raster_asc_file:
        survey_meta.update({
            "data_raster_grid": os.path.basename(raster_asc_file),
            "data_raster_grid_c": "Found"
        })

    # OS-Tile creation if both files exist
    if tb_text_file and raster_asc_file:
        logging.info("Both TB.txt and Raster ASC files found, proceeding with OS-Tile creation")
        os_tile_status = create_os_tiles(tb_text_file)
        survey_meta.update(os_tile_status)
    else:
        logging.error("TB.txt or Raster ASC file not found, cannot create OS-Tiles")
        survey_meta.update({
            "checks_cd_ascii_created_split": "Issue",
            "checks_cd_ascii_created_split_c": "Auto Generation Failed"
        })

    # If all files exist, mark other data as Pass
    if tb_text_file and raster_asc_file and has_photos:
        survey_meta.update({
            "bl_other_data": "Pass",
            "bl_other_data_c": "Found"
        })

    # Run downstream geoprocessing functions
    xy_point_layer_path = create_xy_point_layer(workspace, tb_text_file)
    ras1_path = natural_neighbour_interpolation(workspace, xy_point_layer_path)
    aggregate_points_path = aggregate_points_for_extent(workspace, xy_point_layer_path)
    mask_path = extract_by_mask(workspace, ras1_path, aggregate_points_path)

    return xy_point_layer_path, ras1_path, aggregate_points_path, mask_path

def push_results_to_database(survey_meta, input_text_file, region, bool_baseline_survey):

    from qc_application.utils.name_check_helper_functions import check_data_labeling
    """
    Push survey results to the PostgreSQL database.

    Updates the survey_meta dictionary with labeling results and inserts all
    relevant fields into the `topo_qc.qc_log` table.

    Args:
        survey_meta (dict): Dictionary containing survey metadata and check results.
        input_text_file (str): Path to the input text file used for labeling checks.
        region (str): Survey region identifier (e.g., "PCO").
        bool_baseline_survey (bool): Whether this is a baseline survey.

    Returns:
        None
    """

    push_successful = False

    # Shared metadata
    shared_name = survey_meta.get("gen_name", "Auto")
    shared_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")


    # Run data labeling check
    is_pco = True if region == "PCO" else False
    name_checks = check_data_labeling(input_path=input_text_file, is_baseline=bool_baseline_survey, is_pco=is_pco)

    result = name_checks.get("Result")
    comment = name_checks.get("Comment")

    # Update survey_meta with labeling results
    survey_meta.update({
        "gen_data_labelling": result,
        "gen_data_labelling_c": comment,
        "gen_data_filename": result,
        "gen_data_filename_c": comment
    })

    # Determine columns and values based on survey type
    if not bool_baseline_survey:
        columns = [
            "survey_unit", "survey_type", "completion_date", "survey_received",
            "delivery_reference", "gen_data_labelling", "gen_data_labelling_c",
            "gen_data_filename", "gen_data_filename_c", "gen_metadata", "gen_metadata_c",
            "gen_survey_report", "gen_survey_report_c", "gen_control_observations",
            "gen_date_checked", "gen_name", "data_profile_xyz_txt", "data_profile_xyz_txt_c",
            "checks_pl_point_spacing", "checks_pl_point_spacing_c",
            "checks_pl_seaward_limit", "checks_pl_seaward_limit_c",
            "checks_pl_offline_variation", "checks_pl_offline_variation_c",
            "qc_folder", "checks_pl_photos", "checks_pl_photos_c",
            "checks_date_checked", "checks_name",
        ]

        values = [
            survey_meta.get(k) for k in columns[:len(columns)]
        ]
        # Add shared fields
        values[columns.index("gen_date_checked")] = shared_date
        values[columns.index("gen_name")] = shared_name
        values[columns.index("checks_date_checked")] = shared_date
        values[columns.index("checks_name")] = shared_name

    else:  # Baseline survey
        columns = [
            "survey_unit", "survey_type", "completion_date", "survey_received",
            "delivery_reference", "gen_data_labelling", "gen_data_labelling_c",
            "gen_data_filename", "gen_data_filename_c", "gen_metadata", "gen_metadata_c",
            "gen_survey_report", "gen_survey_report_c", "gen_control_observations",
            "gen_date_checked", "gen_name", "data_baseline_xyz_txt", "data_baseline_xyz_txt_c",
            "checks_cd_ascii_created_split", "checks_cd_ascii_created_split_c",
            "data_raster_grid", "data_raster_grid_c", "bl_xyz_data", "bl_raster_data",
            "bl_profile_photos", "bl_profile_photos_c", "bl_other_data", "bl_other_data_c",
            "data_profile_xyz_txt", "data_profile_xyz_txt_c", "checks_pl_point_spacing",
            "checks_pl_point_spacing_c", "checks_pl_seaward_limit", "checks_pl_seaward_limit_c",
            "checks_pl_offline_variation", "checks_pl_offline_variation_c", "qc_folder",
            "bl_name", "bl_date_checked","checks_date_checked", "checks_name"
        ]

        values = [
            survey_meta.get(k) for k in columns
        ]
        # Add shared fields
        values[columns.index("gen_name")] = shared_name
        values[columns.index("bl_date_checked")] = shared_date
        values[columns.index("checks_date_checked")] = shared_date
        values[columns.index("checks_name")] = shared_name

    # Validate column/value count
    if len(columns) != len(values):
        print("❌ Mismatch: Number of columns and values do not match!")
        for i, (col, val) in enumerate(zip(columns, values)):
            print(f"{i + 1}. {col}: {val}")
        print(f"Columns: {len(columns)} | Values: {len(values)}")
        push_successful = False
        return push_successful

    # Insert into database
    try:
        conn = establish_connection()

        # Build parameterized query
        col_string = ', '.join(columns)
        param_string = ', '.join([f":{col}" for col in columns])
        insert_sql = text(f"INSERT INTO topo_qc.qc_log ({col_string}) VALUES ({param_string})")

        # Build dict for SQLAlchemy parameters
        params = {col: val for col, val in zip(columns, values)}

        conn.execute(insert_sql, params)
        conn.commit()
        print("✅ Data inserted successfully.")
        push_successful= True
        return push_successful


    except Exception as e:
        print(f"❌ Database insertion failed: {e}")
        push_successful = False
        return push_successful

def generate_report(offline_points, lengths_over_spec, depth_checks, bad_feature_codes, workspace, survey_unit):
    """
    Generate a QC report as an Excel workbook with multiple sheets.

    Each DataFrame is written to a separate sheet:
        - 'Offline Points'
        - 'Lengths Over Spec'
        - 'Depth Check'

    Args:
        offline_points (pd.DataFrame): DataFrame containing offline point checks.
        lengths_over_spec (pd.DataFrame): DataFrame containing length checks.
        depth_checks (pd.DataFrame): DataFrame containing depth checks.
        workspace (str): Folder path where the Excel report will be saved.
        survey_unit (str): Identifier for the survey, used in the filename.

    Returns:
        str: Path to the generated Excel report.
    """
    # Ensure workspace exists
    os.makedirs(workspace, exist_ok=True)

    # Path for the Excel report
    xls_path = os.path.join(workspace, f"QCReport_{survey_unit}.xlsx")

    # Create a Pandas Excel writer using OpenPyXL as the engine
    with pd.ExcelWriter(xls_path, engine='openpyxl') as writer:
        offline_points.to_excel(writer, sheet_name='Offline Points', index=False)
        lengths_over_spec.to_excel(writer, sheet_name='Lengths Over Spec', index=False)
        depth_checks.to_excel(writer, sheet_name='Depth Check', index=False)
        bad_feature_codes.to_excel(writer, sheet_name='Depth Check', index=False)

    logging.info(f"QC Report generated at {xls_path} :)")
    return xls_path

def log_paths_to_add_to_map(

    extracted_survey_unit,
    bool_baseline_survey,
    points_file_path,
    offline_line_buffer_path,
    offline_points_path,
    buffer_file_path,
    xy_point_layer_path=None,
    ras1_path=None,
    aggregate_points_path=None,
    mask_path=None
):
    """
    Logs paths to generated shapefiles and updates a dictionary for manual map review.

    Depending on whether the survey is a baseline or not, different paths are recorded.

    Args:

        extracted_survey_unit (str): Survey unit identifier.
        bool_baseline_survey (bool): True if survey is a baseline survey.
        points_file_path (str): Path to the main points shapefile.
        offline_line_buffer_path (str): Path to offline line buffer shapefile.
        offline_points_path (str): Path to offline points shapefile.
        buffer_file_path (str): Path to buffer shapefile.
        xy_point_layer_path (str, optional): Path to XY point layer (baseline only).
        ras1_path (str, optional): Path to raster layer (baseline only).
        aggregate_points_path (str, optional): Path to aggregated points (baseline only).
        mask_path (str, optional): Path to mask layer (baseline only).

    Returns:
        None
    """

    outputs_for_map = {}
    # Log the main paths
    logging.info(
        f"Paths to add to map:\n"
        f"Points File Path: {points_file_path}\n"
        f"Offline Line Buffer Path: {offline_line_buffer_path}\n"
        f"Offline Points Path: {offline_points_path}\n"
        f"Buffer File Path: {buffer_file_path}"
    )

    if not bool_baseline_survey:
        outputs_for_map.update({extracted_survey_unit: [points_file_path,
                                                             offline_line_buffer_path,
                                                             offline_points_path,
                                                             buffer_file_path
                                                             ]})
    else:
        outputs_for_map.update({extracted_survey_unit: [points_file_path,
                                                             offline_line_buffer_path,
                                                             offline_points_path,
                                                             buffer_file_path,
                                                             xy_point_layer_path, ras1_path,
                                                             aggregate_points_path, mask_path
                                                             ]})
    return outputs_for_map
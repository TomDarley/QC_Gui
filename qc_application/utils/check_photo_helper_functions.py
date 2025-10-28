import os
import logging
from typing import Optional, Dict
from typing import Dict, List, Set, Tuple



logger = logging.getLogger(__name__)

def find_photos(input_text_path: str) -> Optional[Dict[str, str]]:
    """Find photos in the 'Other' folder within the main folder of the input path.

    Looks for folders named 'Photos', 'Photographs', or 'Photography' and
    returns a dictionary mapping full paths to file names, ignoring 'Thumbs.db'.

    Args:
        input_text_path (str): Path to an input text file.

    Returns:
        Optional[Dict[str, str]]: Dictionary of photo file paths to file names,
                                  or None if no photos found.
    """
    logger.info("Finding photos in the main folder...")

    # Determine folder paths
    batch_folder = os.path.dirname(input_text_path)
    main_folder = os.path.dirname(batch_folder)
    other_folder = os.path.join(main_folder, 'Other')

    photo_folder_names = ['Photos', 'Photographs', 'Photography']  # Possible photo folder names

    # Find the first existing photo folder
    photo_folder_path = next(
        (os.path.join(other_folder, folder_name) for folder_name in photo_folder_names
         if os.path.exists(os.path.join(other_folder, folder_name))),
        None
    )

    if not photo_folder_path:
        logger.warning("No photo folder found in 'Other'.")
        return None

    # Build dictionary of photos in the folder
    photo_dict = {
        os.path.normpath(os.path.join(photo_folder_path, f)): f
        for f in os.listdir(photo_folder_path)
        if os.path.isfile(os.path.join(photo_folder_path, f)) and f.lower() != 'thumbs.db'
    }

    if not photo_dict:
        logger.warning(f"No photos found in the folder: {photo_folder_path}")
        return None

    logger.info(f"Found {len(photo_dict)} photo(s) in '{photo_folder_path}'")
    return photo_dict

def check_photo_profiles(photo_dict: Dict[str, str], survey_profiles: Set[str]) -> List[str]:
    """
    Check the photo dictionary against the expected survey profiles.

    Args:
        photo_dict: Dictionary mapping full photo path -> filename
        survey_profiles: Set of valid survey profile names

    Returns:
        List of issues found in the photos
    """
    logger.info("Checking the photo profiles...")

    # Ensure survey_profiles is a set
    if isinstance(survey_profiles, list):
        survey_profiles = set(survey_profiles)

    photo_profile_results = []
    invalid_profiles = {}
    invalid_heading = {}
    found_profiles = set()

    # Initialize profile photo status
    profile_photos = {
        profile: {'Up': False, 'Dwn': False, 'E': False, 'W': False, 'N': False, 'S': False}
        for profile in survey_profiles
    }

    # Map possible suffixes to directions
    suffix_map = {
        '_up.': 'Up',
        '_dwn.': 'Dwn',
        '_down': 'Dwn',
        '_e': 'E',
        '_east': 'E',
        '_w.': 'W',
        '_west': 'W',
        '_n.': 'N',
        '_north': 'N',
        '_s.': 'S',
        '_south': 'S'
    }

    # Process each photo
    for path, filename in photo_dict.items():
        profile_name = filename.split('_')[0]
        filename_lower = filename.lower()

        if profile_name not in survey_profiles:
            invalid_profiles[path] = profile_name
            continue

        found_profiles.add(profile_name)

        matched_direction = False
        for suffix, direction in suffix_map.items():
            if suffix in filename_lower:
                profile_photos[profile_name][direction] = True
                matched_direction = True
                break

        if not matched_direction:
            invalid_heading[path] = filename

    # Detect missing profiles
    missing_profiles = survey_profiles - found_profiles
    if missing_profiles:
        logger.warning(f"Missing profiles: {missing_profiles}")
        photo_profile_results.append("Missing_Photo_Profile_Name")

    if invalid_profiles:
        logger.warning(f"Invalid profile names found: {invalid_profiles}")
        photo_profile_results.append("Invalid_Photo_Profile_Name")

    # Check E/W and N/S pairs
    for profile_name, directions in profile_photos.items():
        if directions['E'] != directions['W']:
            photo_profile_results.append("Missing_E_W_Photo_Name")
            break
    for profile_name, directions in profile_photos.items():
        if directions['N'] != directions['S']:
            photo_profile_results.append("Missing_N_S_Photo_Name")
            break

    # Check base set completeness
    for profile_name, directions in profile_photos.items():
        horizontal_complete = directions['E'] and directions['W']
        vertical_complete = directions['N'] and directions['S']
        up_down_complete = directions['Up'] and directions['Dwn']

        if not up_down_complete or not (horizontal_complete or vertical_complete):
            photo_profile_results.append("Incomplete_Base_Set_Of_Photos")
            break

    return photo_profile_results

def check_photo_dates(
    photo_dict: Dict[str, str],
    survey_completion_date: str
) -> Tuple[Dict[str, str], Dict[str, str]]:
    """
    Check that photo filenames contain a date matching the survey completion date.

    Args:
        photo_dict: Dictionary mapping full photo path -> filename
        survey_completion_date: Expected completion date as string (YYYYMMDD)

    Returns:
        Tuple containing:
            - no_date: photos missing a date in the filename
            - incorrect_dates: photos with a date that doesn't match survey_completion_date
    """
    logger.info("Checking the photo dates...")

    no_date: Dict[str, str] = {}
    incorrect_dates: Dict[str, str] = {}

    for photo_path, filename in photo_dict.items():
        basename = os.path.basename(photo_path)
        parts = basename.split('_')

        # Check if second part exists and looks like a date (8 digits)
        if len(parts) > 1 and len(parts[1]) == 8 and parts[1].isdigit():
            photo_date = parts[1]
            if photo_date != survey_completion_date:
                incorrect_dates[photo_path] = photo_date
        else:
            no_date[photo_path] = basename

    logger.info(
        f"Photos missing date: {list(no_date.values())}, "
        f"Photos with incorrect date: {list(incorrect_dates.values())}"
    )

    return no_date, incorrect_dates
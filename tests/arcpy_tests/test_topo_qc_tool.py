import os
import sys
import unittest
from unittest.mock import patch, MagicMock
from qc_application.utils.main_qc_tool_helper_functions import *
from tempfile import NamedTemporaryFile
ARCPY_ENV_PATH = r'C:\Users\darle\AppData\Local\ESRI\conda\envs\arcgispro-py3-clone-2\python.exe'


# ------------------- TESTS -------------------
class TestTopoQCTool(unittest.TestCase):

    def test_arcpy_import(self):
        """Sanity check: arcpy should be importable."""
        import arcpy
        self.assertTrue(True)

    def test_is_baseline_survey_true(self):
        """Path ending with 'tb' should be identified as baseline."""
        path = r"X:\Data\Survey_Topo\Phase4\TSW04\7e\7eSANB1_Sand_Bay\7eSANB1_20220621tb\Batch\7eSANB1_20220621tp.txt"
        self.assertTrue(is_baseline_survey(path))

    def test_is_baseline_survey_false(self):
        """Path not ending with 'tb' should NOT be identified as baseline."""
        path = r"X:\Data\Survey_Topo\Phase4\TSW04\7e\7eSANB1_Sand_Bay\7eSANB1_20221024tip\Batch\7eSANB1_20221024tip.txt"
        self.assertFalse(is_baseline_survey(path))


    def test_bad_baseline_survey_file_path(self):

        path = r"\bad_file.txt"
        self.assertFalse(is_baseline_survey(path))
#
    ## Tests for get_region(path):
    def test_get_region_found(self):
        path = r"X:\Data\Survey_Topo\Phase4\TSW04\7e\7eSANB1_Sand_Bay\7eSANB1_20221024tip\Batch\7eSANB1_20221024tip.txt"
        region = get_region(path)
        self.assertEqual(region, "TSW04")
        self.assertIsNotNone(region)  # Optional extra check

    def test_get_region_not_found(self):
        path = r"X:\Data\Survey_Topo\7eSANB1_20221024tip\Batch\7eSANB1_20221024tip.txt"
        region = get_region(path)
        self.assertIsNone(region)
#
    def test_extract_survey_unit(self):
        from qc_application.utils.main_qc_tool_helper_functions import extract_survey_unit
        input_text = r"X:/Data/Survey_Topo/Phase4/TSW04/7e/7eSANB1_Sand_Bay/7eSANB1_20220621tp/Batch/7eSANB1_20220621tp.txt"
        result = extract_survey_unit(input_text)
        self.assertEqual(result, "SANB1")  # adjust expected value to match input

    ## Tests for makeFileFriendlySurveyUnit(extracted_survey_unit):
    def test_make_file_friendly_survey_unit_with_hyphen(self):

        extracted_survey_unit = "SANB1-EXT"
        expected = "SANB1_EXT"
        result = make_file_friendly_survey_unit(extracted_survey_unit)
        self.assertEqual(result, expected)
#
    def test_make_file_friendly_survey_unit_without_hyphen(self):

        extracted_survey_unit = "SANB1"
        expected = "SANB1"
        result = make_file_friendly_survey_unit(extracted_survey_unit)
        self.assertEqual(result, expected)
#
    def test_make_file_friendly_survey_unit_multiple_hyphens(self):

        extracted_survey_unit = "ABC-123-XYZ"
        expected = "ABC_123_XYZ"

        result = make_file_friendly_survey_unit(extracted_survey_unit)
        self.assertEqual(result, expected)

    @patch("qc_application.utils.main_qc_tool_helper_functions.arcpy.AddMessage")
    def test_get_survey_completion_date_valid_date(self, mock_add_message):
        path = r"X:\Data\Survey_Topo\Phase4\7eSANB1_20220621tp.txt"
        result = get_survey_completion_date(path)
        self.assertEqual(result, "20220621")
        mock_add_message.assert_called_once_with("Survey Date Selected: 20220621")

    @patch("qc_application.utils.main_qc_tool_helper_functions.arcpy.AddMessage")
    def test_get_survey_completion_date_no_underscore(self, mock_add_message):
        path = r"X:\Data\Survey_Topo\Phase4\7eSANB120220621tp.txt"
        result = get_survey_completion_date(path)
        self.assertIsNone(result)
        mock_add_message.assert_not_called()

    @patch("qc_application.utils.main_qc_tool_helper_functions.arcpy.AddMessage")
    def test_get_survey_completion_date_no_date_in_second_part(self, mock_add_message):
        path = r"X:\Data\Survey_Topo\Phase4\7eSANB1_abcdeftp.txt"
        result = get_survey_completion_date(path)
        self.assertIsNone(result)
        mock_add_message.assert_not_called()

    @patch("qc_application.utils.main_qc_tool_helper_functions.arcpy.AddMessage")
    def test_get_survey_completion_date_empty_filename(self, mock_add_message):
        path = ""
        result = get_survey_completion_date(path)
        self.assertIsNone(result)
        mock_add_message.assert_not_called()

    @patch("qc_application.utils.main_qc_tool_helper_functions.arcpy.AddMessage")
    def test_get_survey_completion_date_none_input(self, mock_add_message):
        path = None
        result = get_survey_completion_date(path)
        self.assertIsNone(result)
        mock_add_message.assert_not_called()

    @patch("qc_application.utils.main_qc_tool_helper_functions.Path.exists")
    @patch("qc_application.utils.main_qc_tool_helper_functions.Path.iterdir")
    def test_qc_workspace_found(self, mock_iterdir, mock_exists):
        # Simulate path exists
        mock_exists.return_value = True

        # Mock QC folder in grandparent
        mock_qc_folder = MagicMock()
        mock_qc_folder.is_dir.return_value = True
        mock_qc_folder.name = "QC_Files"
        mock_qc_folder.resolve.return_value = Path(r"C:\Users\darle\Desktop\Data\Survey_Topo\Phase4\TSW02\6d\6d6D2-4_ParSands\6d6D2-4_20211007tip")
        mock_iterdir.return_value = [mock_qc_folder]

        path = r"C:\Users\darle\Desktop\Data\Survey_Topo\Phase4\TSW02\6d\6d6D2-4_ParSands\6d6D2-4_20211007tip\Batch\6d6D2-4_20211007tip.txt"
        result = get_qc_workspace(path)
        self.assertEqual(result, str(mock_qc_folder.resolve()))

    @patch("qc_application.utils.main_qc_tool_helper_functions.Path.exists")
    @patch("qc_application.utils.main_qc_tool_helper_functions.Path.iterdir")
    def test_qc_workspace_not_found(self, mock_iterdir, mock_exists):
        mock_exists.return_value = True

        # No QC folder
        mock_folder = MagicMock()
        mock_folder.is_dir.return_value = True
        mock_folder.name = "OtherFolder"
        mock_iterdir.return_value = [mock_folder]

        path = r"C:\Users\darle\Desktop\Data\Survey_Topo\Phase4\TSW02\6d\6d6D2-4_ParSands\6d6D2-4_20211007tip\Batch\6d6D2-4_20211007tip.txt"
        result = get_qc_workspace(path)
        self.assertIsNone(result)

    @patch("qc_application.utils.main_qc_tool_helper_functions.Path.exists")
    def test_invalid_input_path(self, mock_exists):
        mock_exists.return_value = False
        path = r"C:\Data\Project\Survey\nonexistent_file.txt"
        result = get_qc_workspace(path)
        self.assertIsNone(result)

class TestSurveyUnitFunctions(unittest.TestCase):

    @patch(
        "qc_application.utils.main_qc_tool_helper_functions.check_survey_unit_in_shapefile"
    )
    @patch(
        "qc_application.utils.main_qc_tool_helper_functions.extract_survey_unit"
    )
    def test_valid_survey_unit(self, mock_extract, mock_check):
        """
        Test when a survey unit can be extracted and exists in the shapefile.
        """
        mock_extract.return_value = "SANB1"
        mock_check.return_value = True

        path = r"X:\Data\Survey_Topo\Phase4\TSW04\7eSANB1_20220621tp.txt"
        shapefile = r"X:\Data\Survey_Topo\Phase4\SurveyProfileLines.shp"

        result = get_input_survey_unit(path, shapefile)
        self.assertEqual(result, "SANB1")
        mock_extract.assert_called_once_with(path)
        mock_check.assert_called_once_with("SANB1", shapefile)

    @patch(
        "qc_application.utils.main_qc_tool_helper_functions.check_survey_unit_in_shapefile"
    )
    @patch(
        "qc_application.utils.main_qc_tool_helper_functions.extract_survey_unit"
    )
    def test_survey_unit_not_in_shapefile(self, mock_extract, mock_check):
        """
        Test when a survey unit is extracted but not found in the shapefile.
        """
        mock_extract.return_value = "SANB1"
        mock_check.return_value = False

        path = r"X:\Data\Survey_Topo\Phase4\7eSANB1_20220621tp.txt"
        shapefile = r"X:\Data\Survey_Topo\Phase4\SurveyProfileLines.shp"

        result = get_input_survey_unit(path, shapefile)
        self.assertIsNone(result)
        mock_extract.assert_called_once_with(path)
        mock_check.assert_called_once_with("SANB1", shapefile)

    @patch(
        "qc_application.utils.main_qc_tool_helper_functions.check_survey_unit_in_shapefile"
    )
    @patch(
        "qc_application.utils.main_qc_tool_helper_functions.extract_survey_unit"
    )
    def test_cannot_extract_survey_unit(self, mock_extract, mock_check):
        """
        Test when no survey unit can be extracted from the input path.
        """
        mock_extract.return_value = None
        mock_check.return_value = True  # Should not matter

        path = r"X:\Data\Survey_Topo\Phase4\bad_file.txt"
        shapefile = r"X:\Data\Survey_Topo\Phase4\SurveyProfileLines.shp"

        result = get_input_survey_unit(path, shapefile)
        self.assertIsNone(result)
        mock_extract.assert_called_once_with(path)
        mock_check.assert_not_called()  # check should not run if extr
#
class TestSurveyCellFunctions(unittest.TestCase):

    # -------------------- extract_survey_cell --------------------
    def test_extract_valid_filename(self):
        path = r"X:\Data\Survey_Topo\Phase4\7eSANB1_20220621tp.txt"
        result = extract_survey_cell(path)
        self.assertEqual(result, "7e")

    def test_extract_short_filename(self):
        path = r"X:\Data\Survey_Topo\Phase4\a.txt"
        result = extract_survey_cell(path)
        self.assertIsNone(result)

    def test_extract_exactly_10_chars_filename(self):
        path = r"X:\Data\Survey_Topo\Phase4\abcdefghij.txt"
        result = extract_survey_cell(path)
        self.assertEqual(result, "ab")

    def test_extract_invalid_input_none(self):
        path = None
        result = extract_survey_cell(path)
        self.assertIsNone(result)

    # -------------------- check_cell_in_shapefile --------------------
    @patch("qc_application.utils.main_qc_tool_helper_functions.arcpy.Exists")
    @patch("qc_application.utils.main_qc_tool_helper_functions.arcpy.da.SearchCursor")
    def test_check_cell_found(self, mock_cursor, mock_exists):
        # Simulate shapefile exists
        mock_exists.return_value = True
        # Simulate cells in shapefile
        mock_cursor.return_value.__enter__.return_value = [("7e",), ("8f",)]
        result = check_cell_in_shapefile("7e", "fake_shapefile.shp")
        self.assertTrue(result)

    @patch("qc_application.utils.main_qc_tool_helper_functions.arcpy.Exists")
    @patch("qc_application.utils.main_qc_tool_helper_functions.arcpy.da.SearchCursor")
    def test_check_cell_not_found(self, mock_cursor, mock_exists):
        mock_exists.return_value = True
        mock_cursor.return_value.__enter__.return_value = [("8f",), ("9g",)]
        result = check_cell_in_shapefile("7e", "fake_shapefile.shp")
        self.assertFalse(result)

    @patch("qc_application.utils.main_qc_tool_helper_functions.arcpy.Exists")
    def test_check_cell_shapefile_not_exist(self, mock_exists):
        mock_exists.return_value = False
        result = check_cell_in_shapefile("7e", "missing_shapefile.shp")
        self.assertFalse(result)

    # -------------------- get_survey_cell --------------------
    @patch("qc_application.utils.main_qc_tool_helper_functions.check_cell_in_shapefile")
    def test_get_survey_cell_valid(self, mock_check):
        mock_check.return_value = True
        path = r"X:\Data\Survey_Topo\Phase4\7eSANB1_20220621tp.txt"
        shapefile = r"fake_shapefile.shp"
        result = get_survey_cell(path, shapefile)
        self.assertEqual(result, "7e")

    @patch("qc_application.utils.main_qc_tool_helper_functions.check_cell_in_shapefile")
    def test_get_survey_cell_not_in_shapefile(self, mock_check):
        mock_check.return_value = False
        path = r"X:\Data\Survey_Topo\Phase4\7eSANB1_20220621tp.txt"
        shapefile = r"fake_shapefile.shp"
        result = get_survey_cell(path, shapefile)
        self.assertIsNone(result)

    def test_get_survey_cell_extract_fail(self):
        path = r"X:\Data\Survey_Topo\Phase4\a.txt"  # too short
        shapefile = r"fake_shapefile.shp"
        result = get_survey_cell(path, shapefile)
        self.assertIsNone(result)

class TestUniversalTextFileConverter(unittest.TestCase):

    def test_successful_conversion(self):
        # Create a temporary tab-separated file
        with NamedTemporaryFile(mode='w+', delete=False, suffix='.txt') as temp_file:
            temp_file.write(
                "Chainage\tEasting\tNorthing\tElevation_OD\tCode\tProfile Reg_ID\n"
                "0\t1000\t2000\t10\tA\t001\n"
                "1\t1010\t2010\t12\tB\t002\n"
            )
            temp_file_path = temp_file.name

        try:
            df = universal_text_file_converter(temp_file_path)
            # Check resulting DataFrame columns
            self.assertIn('Easting', df.columns)
            self.assertIn('Northing', df.columns)
            self.assertIn('Elevation', df.columns)
            self.assertIn('FC', df.columns)
            self.assertIn('Reg_ID', df.columns)
            self.assertIn('Unique_ID', df.columns)
            # Chainage should be removed
            self.assertNotIn('Chainage', df.columns)
            # Check Reg_ID formatting
            self.assertTrue(all(df['Reg_ID'].str.startswith('_')))
        finally:
            os.remove(temp_file_path)

    def test_missing_headers(self):
        # File missing 'Elevation_OD'
        with NamedTemporaryFile(mode='w+', delete=False, suffix='.txt') as temp_file:
            temp_file.write(
                "Chainage\tEasting\tNorthing\tCode\tProfile Reg_ID\n"
                "0\t1000\t2000\tA\t001\n"
            )
            temp_file_path = temp_file.name

        try:
            df = universal_text_file_converter(temp_file_path)
            self.assertTrue(df.empty)
        finally:
            os.remove(temp_file_path)

    def test_invalid_file_path(self):
        # Path does not exist
        df = universal_text_file_converter(r"C:\nonexistent_path\file.txt")
        self.assertTrue(df.empty)

class TestGetMLSW(unittest.TestCase):

    @patch("qc_application.utils.main_qc_tool_helper_functions.logging.info")
    def test_mlsw_found(self, mock_log_info):
        mlsw_dict = {"7e6D2": 42, "8f6D3": 99}
        result = get_mlsw("6D2", "7e", mlsw_dict)
        self.assertEqual(result, 42)
        mock_log_info.assert_called_once_with("MLSW set to 42")

    @patch("qc_application.utils.main_qc_tool_helper_functions.logging.warning")
    def test_mlsw_not_found(self, mock_log_warning):
        mlsw_dict = {"8f6D3": 99}
        result = get_mlsw("6D2", "7e", mlsw_dict)
        self.assertIsNone(result)
        mock_log_warning.assert_called_once_with("MLSW value not found for key: 7e6D2")

class TestCreatePointFileName(unittest.TestCase):

    def test_create_file_name_standard(self):
        extracted_cell = "7e"
        file_friendly_survey_unit = "6D2"
        survey_completion_date = "20211007"
        expected = "7e6D2_20211007_tip_Auto.shp"
        result = create_point_file_name(extracted_cell, file_friendly_survey_unit, survey_completion_date)
        self.assertEqual(result, expected)

    def test_create_file_name_different_inputs(self):
        extracted_cell = "8f"
        file_friendly_survey_unit = "9G1"
        survey_completion_date = "20230515"
        expected = "8f9G1_20230515_tip_Auto.shp"
        result = create_point_file_name(extracted_cell, file_friendly_survey_unit, survey_completion_date)
        self.assertEqual(result, expected)

    def test_empty_strings(self):
        extracted_cell = ""
        file_friendly_survey_unit = ""
        survey_completion_date = ""
        expected = "_ _tip_Auto.shp".replace(" ", "")  # yields "__tip_Auto.shp"
        result = create_point_file_name(extracted_cell, file_friendly_survey_unit, survey_completion_date)
        self.assertEqual(result, expected)

class TestMakeXYEventLayer(unittest.TestCase):

    @patch("qc_application.utils.main_qc_tool_helper_functions.arcpy.management.XYTableToPoint")
    @patch("qc_application.utils.main_qc_tool_helper_functions.arcpy.Exists")
    @patch("qc_application.utils.main_qc_tool_helper_functions.os.remove")
    @patch("qc_application.utils.main_qc_tool_helper_functions.os.path.exists")
    def test_xy_layer_creation(self, mock_exists, mock_remove, mock_exists_arcpy, mock_xy):
        # Setup mocks
        mock_exists.return_value = True
        mock_exists_arcpy.return_value = False

        df = pd.DataFrame({"Easting": [1000], "Northing": [2000], "Elevation": [10]})
        workspace = r"C:\temp"
        output_file_name = "points.shp"

        result = make_xy_event_layer(df, workspace, output_file_name)

        # Check that XYTableToPoint was called
        mock_xy.assert_called_once()
        # Check the function returns the correct path
        self.assertEqual(result, r"C:\temp\points.shp")
        # Check temporary file removal is attempted
        mock_remove.assert_called_once_with(r"C:\temp\temp.csv")

class TestFeatureCodeCheck(unittest.TestCase):

    @patch("qc_application.utils.main_qc_tool_helper_functions.logging.info")
    def test_all_valid_codes(self, mock_log_info):
        df = pd.DataFrame({
            "FC": ["S", "M", "G", "GS", "ms", "hw"]
        })
        result = feature_code_check(df)
        # Expect empty DataFrame
        self.assertTrue(result.empty)
        mock_log_info.assert_called_once_with("All feature codes correctly defined. ✅")

    @patch("qc_application.utils.main_qc_tool_helper_functions.logging.warning")
    def test_some_invalid_codes(self, mock_log_warning):
        df = pd.DataFrame({
            "FC": ["S", "X", "INVALID", "MS", "ZZ"]
        })
        result = feature_code_check(df)
        # Expect DataFrame with one invalid code
        self.assertEqual(len(result), 1)
        self.assertEqual(result.iloc[0]['FC'], "INVALID")
        self.assertEqual(result.iloc[0]['Index'], 2)
        mock_log_warning.assert_called_once()

class TestExtractInterimLines(unittest.TestCase):

    @patch("qc_application.utils.main_qc_tool_helper_functions.arcpy.Select_analysis")
    @patch("qc_application.utils.main_qc_tool_helper_functions.logging.info")
    def test_extract_interim_lines_interim(self, mock_log_info, mock_select):
        survey_profile_lines_shp = r"C:\temp\lines.shp"
        workspace = r"C:\temp"
        extracted_cell = "7e"
        file_friendly_survey_unit = "6D2"

        expected_output = os.path.join(
            workspace,
            f"SelectedInterimLines_{extracted_cell}{file_friendly_survey_unit}_Auto.shp"
        )

        result = extract_interim_lines(
            survey_profile_lines_shp, workspace, extracted_cell, file_friendly_survey_unit
        )

        self.assertEqual(result, expected_output)
        # Check that arcpy.Select_analysis was called with correct args
        mock_select.assert_called_once_with(
            survey_profile_lines_shp,
            expected_output,
            "SURVEY_UNT = '6D2' AND INTERIM = 'YES'"
        )
        # Optional: check logging called
        mock_log_info.assert_any_call("Using query: SURVEY_UNT = '6D2' AND INTERIM = 'YES'")

    @patch("qc_application.utils.main_qc_tool_helper_functions.arcpy.Select_analysis")
    @patch("qc_application.utils.main_qc_tool_helper_functions.logging.info")
    def test_extract_interim_lines_baseline(self, mock_log_info, mock_select):
        survey_profile_lines_shp = r"C:\temp\lines.shp"
        workspace = r"C:\temp"
        extracted_cell = "7e"
        file_friendly_survey_unit = "6D2"

        expected_output = os.path.join(
            workspace,
            f"SelectedInterimLines_{extracted_cell}{file_friendly_survey_unit}_Auto.shp"
        )

        result = extract_interim_lines(
            survey_profile_lines_shp, workspace, extracted_cell, file_friendly_survey_unit, is_baseline_survey=True
        )

        self.assertEqual(result, expected_output)
        mock_select.assert_called_once_with(
            survey_profile_lines_shp,
            expected_output,
            "SURVEY_UNT = '6D2' AND BASELINE = 'YES'"
        )
        mock_log_info.assert_any_call("Using query: SURVEY_UNT = '6D2' AND BASELINE = 'YES'")

class TestCreateOfflinePointsFileName(unittest.TestCase):

    def test_create_offline_buffer_file_name_default_tolerance(self):
        region = "TSW02"
        workspace = r"C:\temp"
        extracted_cell = "7e"
        file_friendly_survey_unit = "6D2"

        expected_path = os.path.join(
            workspace, "Buffer_01m_7e6D2_Auto.shp"
        )

        result = create_offline_buffer_file_name(region, workspace, extracted_cell, file_friendly_survey_unit)
        self.assertEqual(result, expected_path)

    def test_generate_offline_points_path(self):
        workspace = r"C:\temp"
        extracted_cell = "7e"
        file_friendly_survey_unit = "6D2"

        expected_path = os.path.join(workspace, "Offline_points_7e6D2_Auto.shp")
        result = generate_offline_points_path(workspace, extracted_cell, file_friendly_survey_unit)
        self.assertEqual(result, expected_path)

class TestOfflineBufferFileNameFunctions(unittest.TestCase):

    def test_create_offline_buffer_file_name_known_region(self):
        region = "TSW_IoS"  # In tolerance_map
        workspace = r"C:\temp"
        extracted_cell = "7e"
        file_friendly_survey_unit = "6D2"

        expected_path = os.path.join(workspace, "Buffer_03m_7e6D2_Auto.shp")
        result = create_offline_buffer_file_name(region, workspace, extracted_cell, file_friendly_survey_unit)
        self.assertEqual(result, expected_path)

    def test_create_offline_buffer_file_name_default_tolerance(self):
        region = "TSW02"  # Not in tolerance_map
        workspace = r"C:\temp"
        extracted_cell = "7e"
        file_friendly_survey_unit = "6D2"

        expected_path = os.path.join(workspace, "Buffer_01m_7e6D2_Auto.shp") # default 0.1 → 10
        result = create_offline_buffer_file_name(region, workspace, extracted_cell, file_friendly_survey_unit)
        self.assertEqual(result, expected_path)

class TestCreateOfflineBuffer(unittest.TestCase):

    @patch("qc_application.utils.main_qc_tool_helper_functions.arcpy")
    def test_create_offline_buffer_TSW_IoS(self, mock_arcpy):
        region = "TSW_IoS"
        offline_line_buffer_path = r"C:\temp\buffer.shp"
        selected_interim_lines = r"C:\temp\lines.shp"

        create_offline_buffer(region, offline_line_buffer_path, selected_interim_lines)

        # Check that Buffer_analysis was called with correct parameters
        mock_arcpy.Buffer_analysis.assert_called_once_with(
            in_features=selected_interim_lines,
            out_feature_class=offline_line_buffer_path,
            buffer_distance_or_field=0.03
        )

    @patch("qc_application.utils.main_qc_tool_helper_functions.arcpy")
    def test_create_offline_buffer_TSW_PCO(self, mock_arcpy):
        region = "TSW_PCO"
        offline_line_buffer_path = r"C:\temp\buffer.shp"
        selected_interim_lines = r"C:\temp\lines.shp"

        create_offline_buffer(region, offline_line_buffer_path, selected_interim_lines)

        # Check that Buffer_analysis was called with correct parameters
        mock_arcpy.Buffer_analysis.assert_called_once_with(
            in_features=selected_interim_lines,
            out_feature_class=offline_line_buffer_path,
            buffer_distance_or_field=0.03
        )


    @patch("qc_application.utils.main_qc_tool_helper_functions.arcpy")
    def test_create_offline_buffer_default_region(self, mock_arcpy):
        region = "TSW02"  # not in buffer_distances → default 0.1
        offline_line_buffer_path = r"C:\temp\buffer.shp"
        selected_interim_lines = r"C:\temp\lines.shp"

        create_offline_buffer(region, offline_line_buffer_path, selected_interim_lines)

        mock_arcpy.Buffer_analysis.assert_called_once_with(
            in_features=selected_interim_lines,
            out_feature_class=offline_line_buffer_path,
            buffer_distance_or_field=0.1
        )

class TestGenerateOfflinePointsPath(unittest.TestCase):

    def test_generate_offline_points_path(self):
        workspace = r"C:\temp"
        extracted_cell = "7e"
        file_friendly_survey_unit = "6D2"

        expected_path = os.path.join(workspace, "Offline_points_7e6D2_Auto.shp")
        result = generate_offline_points_path(workspace, extracted_cell, file_friendly_survey_unit)

        self.assertEqual(result, expected_path)

class TestCheckPointsLieOnCorrectProfileLines(unittest.TestCase):

    @patch("qc_application.utils.main_qc_tool_helper_functions.arcpy")
    def test_all_points_match(self, mock_arcpy):
        # Mock the SearchCursor to return matching reg_id and REGIONAL_N
        mock_cursor = MagicMock()
        mock_cursor.__enter__.return_value = [("A", "A"), ("B", "B")]
        mock_arcpy.da.SearchCursor.return_value = mock_cursor

        result = check_points_lie_on_correct_profile_lines("points.shp", "buffer.shp")
        self.assertTrue(result)

    @patch("qc_application.utils.main_qc_tool_helper_functions.arcpy")
    def test_some_points_mismatch(self, mock_arcpy):
        # One point does not match
        mock_cursor = MagicMock()
        mock_cursor.__enter__.return_value = [("A", "A"), ("B", "C")]
        mock_arcpy.da.SearchCursor.return_value = mock_cursor

        result = check_points_lie_on_correct_profile_lines("points.shp", "buffer.shp")
        self.assertFalse(result)

    @patch("qc_application.utils.main_qc_tool_helper_functions.arcpy")
    def test_no_intersections(self, mock_arcpy):
        # No intersecting points → should return True
        mock_cursor = MagicMock()
        mock_cursor.__enter__.return_value = []
        mock_arcpy.da.SearchCursor.return_value = mock_cursor

        result = check_points_lie_on_correct_profile_lines("points.shp", "buffer.shp")
        self.assertTrue(result)

class TestSpacingCheck(unittest.TestCase):

    def test_no_spacing_issues(self):
        # Points close together within tolerance
        df = pd.DataFrame({
            'Reg_ID': ['A', 'A', 'A'],
            'Easting': [0, 0.5, 1.0],
            'Northing': [0, 0.5, 1.0]
        })
        spacing_unit_error = 2.0
        result = spacing_check(df, spacing_unit_error)
        self.assertTrue(result.empty)

    def test_some_spacing_issues(self):
        # One distance exceeds tolerance
        df = pd.DataFrame({
            'Reg_ID': ['A', 'A', 'A'],
            'Easting': [0, 1, 5],
            'Northing': [0, 0, 0]
        })
        spacing_unit_error = 3.0
        result = spacing_check(df, spacing_unit_error)
        # The second distance is 4 > 3, should appear
        self.assertIn('A', result.index)
        self.assertEqual(result.iloc[0, 0], 4.0)

    def test_multiple_profiles(self):
        df = pd.DataFrame({
            'Reg_ID': ['A', 'A', 'B', 'B'],
            'Easting': [0, 10, 0, 1],
            'Northing': [0, 0, 0, 0]
        })
        spacing_unit_error = 5.0
        result = spacing_check(df, spacing_unit_error)
        # Only profile A has distance over 5
        self.assertIn('A', result.index)
        self.assertNotIn('B', result.index)

    def test_missing_coordinates(self):
        df = pd.DataFrame({
            'Reg_ID': ['A', 'A', 'A'],
            'Easting': [0, None, 5],
            'Northing': [0, 0, None]
        })
        spacing_unit_error = 1.0
        result = spacing_check(df, spacing_unit_error)
        # All rows with NaN are ignored, so nothing should appear
        self.assertTrue(result.empty)

class TestCheckMadeDepth(unittest.TestCase):

    def test_all_profiles_make_depth(self):
        df = pd.DataFrame({
            "Reg_ID": ["A", "A", "B", "B"],
            "Elevation": [2.0, 1.5, 3.0, 2.5]
        })
        mlsw_value = 3.5
        result = check_made_depth(df, mlsw_value)
        self.assertTrue(result.empty)

    def test_some_profiles_fail_depth(self):
        df = pd.DataFrame({
            "Reg_ID": ["A", "A", "B", "B"],
            "Elevation": [4.0, 4.5, 2.0, 2.5]
        })
        mlsw_value = 3.0
        result = check_made_depth(df, mlsw_value)
        # Only profile A should have passed; profile B failed
        self.assertEqual(list(result["Reg_ID"]), ["A"])

    def test_empty_dataframe(self):
        df = pd.DataFrame(columns=["Reg_ID", "Elevation"])
        mlsw_value = 3.0
        result = check_made_depth(df, mlsw_value)
        self.assertTrue(result.empty)

    def test_non_numeric_elevation(self):
        df = pd.DataFrame({
            "Reg_ID": ["A", "B"],
            "Elevation": ["x", 2.0]
        })
        mlsw_value = 1.5
        result = check_made_depth(df, mlsw_value)
        # Only profile B has numeric elevation; profile A should be ignored
        self.assertEqual(list(result["Reg_ID"]), ["B"])

# Run the tests only when script is run directly
if __name__ == '__main__':
    # Suppress print inside tested functions, but allow test runner output
    with patch("builtins.print"):
        unittest.main(verbosity=2)

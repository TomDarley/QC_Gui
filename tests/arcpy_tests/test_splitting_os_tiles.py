import pytest
import os
import shutil
from unittest.mock import patch, MagicMock

# Import the refactored class

from qc_application.services.topo_splitting_os_tiles_service import SplitOSTiles
@pytest.fixture
def temp_paths(tmp_path):
    """
    This fixture creates a temporary directory structure for testing.
    It simulates the folder layout the SplitOSTiles class expects, including 'Batch' and 'Other' subdirectories
    with mock files, and returns a dictionary of the paths. This ensures tests are isolated and don't
    rely on the actual file system.
    """
    tb_folder = tmp_path / "7cSAUN1_20240706tb"
    batch_dir = tb_folder / "Batch"
    other_dir = tb_folder / "Other"

    batch_dir.mkdir(parents=True)
    other_dir.mkdir(parents=True)

    (batch_dir / "SA_20240706tb.txt").touch()
    (batch_dir / "TB_20240706tb.txt").touch()

    return {
        "tb_folder": str(tb_folder),
        "ostile_path": "mock/ostile/path",
        "batch_path": str(batch_dir),
        "other_path": str(other_dir),
    }

@pytest.fixture
def split_os_tiles_instance(temp_paths):
    """
    This fixture creates a SplitOSTiles object for use in tests.
    It provides a pre-initialized instance, which reduces code duplication across tests that need a
    working object to test methods.
    """
    return SplitOSTiles(
        tb_folder_path=temp_paths["tb_folder"],
        ostile_path=temp_paths["ostile_path"]
    )

class TestSplitOSTiles:
    def mock_exists_side_effect(path):
        """
        A helper function for patching os.path.exists.
        It's used to simulate a scenario where the 'Batch' directory does not exist.
        """
        if "Batch" in path:
            return False
        # Return True for all other paths to allow other checks to pass
        return True

    @pytest.mark.arcpy
    @patch("os.path.exists", side_effect=mock_exists_side_effect)
    def test_init_fails_if_batch_path_missing(self, mock_exists, temp_paths):
        """
        This test verifies that the SplitOSTiles constructor raises a FileNotFoundError
        when the 'Batch' directory is missing.
        It uses a mocked os.path.exists that returns False only for the path containing 'Batch'.
        """
        with pytest.raises(FileNotFoundError, match="Batch path does not exist"):
            SplitOSTiles(
                tb_folder_path=temp_paths["tb_folder"],
                ostile_path=temp_paths["ostile_path"]
            )

    def mock_other_path_exists_side_effect(path):
        """
        A helper function for patching os.path.exists for the other path test.
        It's used to simulate a scenario where the 'Other' directory does not exist.
        """
        if "Other" in path:
            return False
        # Return True for all other paths to allow other checks to pass
        return True

    @pytest.mark.arcpy
    @patch("os.path.exists", side_effect=mock_other_path_exists_side_effect)
    def test_init_fails_if_other_path_missing(self, mock_exists, temp_paths):
        """
        This test verifies that the SplitOSTiles constructor raises a FileNotFoundError
        when the 'Other' directory is missing.
        It uses a mocked os.path.exists that returns False only for the path containing 'Other'.
        """
        with pytest.raises(FileNotFoundError, match="Other path does not exist"):
            SplitOSTiles(
                tb_folder_path=temp_paths["tb_folder"],
                ostile_path=temp_paths["ostile_path"]
            )

    @pytest.mark.arcpy
    def test_init_fails_if_date_pattern_missing(self, temp_paths):
        """
        This test ensures that the constructor raises a ValueError if the input path
        does not contain a valid date pattern. It passes a mock path without the pattern.
        """
        with pytest.raises(ValueError, match="Could not find a valid date pattern"):
            SplitOSTiles(
                tb_folder_path="mock/path/without/date",
                ostile_path=temp_paths["ostile_path"]
            )

    @pytest.mark.arcpy
    @patch("os.listdir", return_value=["file1.zip", "file2.jpg"])
    def test_get_os_tile_names_raises_error_if_no_files_found(self, mock_listdir, split_os_tiles_instance):
        """
        This test checks that the get_os_tile_names method raises a FileNotFoundError
        if no files with the '.tb' extension are found. It mocks os.listdir to return a list
        of unrelated files.
        """
        with pytest.raises(FileNotFoundError, match="No 'tb' files could be found"):
            split_os_tiles_instance.get_os_tile_names()

    @pytest.mark.arcpy
    @patch("os.listdir", return_value=["SY6575_20240706tb.txt", "SY6576_20240706tb.txt"])
    def test_get_os_tile_names_success(self, mock_listdir, split_os_tiles_instance):
        """
        This test verifies that the get_os_tile_names method successfully extracts
        the correct OS tile names from the file names in the directory.
        It mocks os.listdir to return a list of valid 'tb' files.
        """
        split_os_tiles_instance.get_os_tile_names()
        expected_tiles = ["SY6575", "SY6576"]
        assert sorted(split_os_tiles_instance.tile_names) == sorted(expected_tiles)

    @pytest.mark.arcpy
    @patch("arcpy.SelectLayerByAttribute_management")
    @patch("arcpy.management.SplitRaster", side_effect=[Exception, Exception, None])
    @patch("os.path.isdir", return_value=True)
    @patch("shutil.rmtree")
    def test_split_ascii_into_rasters_retry_and_success(self, mock_rmtree, mock_isdir, mock_split, mock_select,
                                                        split_os_tiles_instance):
        """
        This test checks the retry mechanism of the split_ascii_into_rasters method.
        It mocks arcpy.management.SplitRaster to fail twice and then succeed, verifying that the
        method correctly retries the operation.
        """
        split_os_tiles_instance.tile_names = ["SA"]
        split_os_tiles_instance.inAscii = "mock/path/raster.asc"
        split_os_tiles_instance.split_ascii_into_rasters()
        assert mock_split.call_count == 3

    @pytest.mark.arcpy
    @patch("arcpy.SelectLayerByAttribute_management")
    @patch("arcpy.management.SplitRaster", side_effect=Exception("Failed split"))
    @patch("os.path.isdir", return_value=True)
    @patch("shutil.rmtree")
    def test_split_ascii_into_rasters_raises_error_after_retries(self, mock_rmtree, mock_isdir, mock_split, mock_select,
                                                                 split_os_tiles_instance):
        """
        This test verifies that the split_ascii_into_rasters method raises a RuntimeError
        if it fails to split the raster after all retries.
        It mocks arcpy.management.SplitRaster to always raise an exception.
        """
        split_os_tiles_instance.tile_names = ["SA"]
        split_os_tiles_instance.inAscii = "mock/path/raster.asc"
        with pytest.raises(RuntimeError, match="Not all rasters were created successfully."):
            split_os_tiles_instance.split_ascii_into_rasters()

    @pytest.mark.arcpy
    @patch("arcpy.RasterToASCII_conversion", side_effect=[Exception, Exception, None])
    def test_covert_rasters_to_ascii_retry_and_success(self, mock_rascii, split_os_tiles_instance):
        """
        This test checks the retry mechanism for converting rasters to ASCII.
        It mocks arcpy.RasterToASCII_conversion to fail twice and then succeed,
        ensuring the method handles transient failures.
        """
        split_os_tiles_instance.created_rasters = ["mock/path/SA_00"]
        split_os_tiles_instance.covert_rasters_to_ascii()
        assert mock_rascii.call_count == 3
        assert len(split_os_tiles_instance.created_ascii) == 1

    @pytest.mark.arcpy
    @patch("arcpy.RasterToASCII_conversion", side_effect=Exception("Failed conversion"))
    def test_covert_rasters_to_ascii_raises_error_after_retries(self, mock_rascii, split_os_tiles_instance):
        """
        This test verifies that the covert_rasters_to_ascii method raises a RuntimeError
        if it fails to convert rasters to ASCII after all retries.
        It mocks arcpy.RasterToASCII_conversion to always raise an exception.
        """
        split_os_tiles_instance.created_rasters = ["mock/path/SA_00"]
        with pytest.raises(RuntimeError, match="Not all rasters were successfully converted to ASCII."):
            split_os_tiles_instance.covert_rasters_to_ascii()

    @patch("shutil.move")
    @patch("os.listdir", return_value=["file1.asc.xml", "file2.prj", "image.jpg"])
    @patch("shutil.rmtree")
    @pytest.mark.arcpy
    def test_clean_up_files_moves_correct_files_and_deletes_folder(self, mock_rmtree, mock_listdir, mock_move,
                                                                   split_os_tiles_instance):
        """
        This test verifies that the clean_up_files method correctly moves the necessary files
        and deletes the temporary folder. It mocks os.listdir, shutil.move, and shutil.rmtree
        to check if they were called with the expected arguments.
        """
        split_os_tiles_instance.clean_up_files()
        assert mock_move.call_count == 4
        mock_rmtree.assert_called_once_with(split_os_tiles_instance.folder_to_delete)

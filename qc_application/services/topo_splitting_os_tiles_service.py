import arcpy
import os
import re
import shutil
import time


class SplitOSTiles:
    """New version of the OS tile split tool. Added retry, better logging, and error handling.
    Requires arcpy to be used as the Python interpreter."""

    def __init__(self, tb_folder_path, ostile_path):
        self.tb_folder_path = tb_folder_path
        self.ostile_path = ostile_path
        arcpy.env.overwriteOutput = True

        self.batch_path = os.path.join(self.tb_folder_path, "Batch")
        self.other_path = os.path.join(self.tb_folder_path, "Other")

        date_match = re.search(r'\d{8}\w[a-z]', os.path.basename(self.tb_folder_path))
        if not date_match:
            raise ValueError(f"Could not find a valid date pattern in path: {self.tb_folder_path}")
        self.date = date_match.group()

        self.inRaster1 = os.path.basename(self.tb_folder_path)
        self.inAscii = os.path.join(self.other_path, f"{self.inRaster1}.asc")

        if not os.path.exists(self.batch_path):
            raise FileNotFoundError(f"Batch path does not exist: {self.batch_path}")
        if not os.path.exists(self.other_path):
            raise FileNotFoundError(f"Other path does not exist: {self.other_path}")

        self.folder_to_delete = os.path.join(os.path.expanduser('~'), 'Downloads', "Delete_me")
        if not os.path.exists(self.folder_to_delete):
            os.makedirs(self.folder_to_delete, exist_ok=True)

        self.tile_names = []
        self.created_rasters = []
        self.created_ascii = []  # FIX: This was missing in your provided code!

    def get_os_tile_names(self):
        # ... (no changes needed here, the logic is fine)
        for batch_file in os.listdir(self.batch_path):
            pattern = re.compile(r'[A-Z]{2}\d{4}')
            matches = pattern.findall(batch_file)
            if matches:
                self.tile_names.append(batch_file.split("_")[0])

        if not self.tile_names:
            raise FileNotFoundError(
                "No 'tb' files could be found. Check if the text files with OS tiles in the file name exist.")
        print(f"Will split into: {self.tile_names}")
        return self.tile_names

    def split_ascii_into_rasters(self):
        # ... (no changes needed here, the logic is fine but the test needs to be fixed)
        print("Attempting to split ascii into rasters.....")
        successful_splits = 0

        for index, tile_name in enumerate(self.tile_names, start=1):
            print(f"Attempting to split {self.inAscii} for tile: {tile_name}")
            os_selection = arcpy.SelectLayerByAttribute_management(self.ostile_path, 'NEW_SELECTION',
                                                                   f"NAME = '{tile_name}'")
            out_path = os.path.join(self.other_path, f"{tile_name}_00")
            if arcpy.Exists(out_path):
                print(f"Raster already exists: {out_path}. Deleting before split.")
                arcpy.management.Delete(out_path)


            retry_count = 0

            while retry_count < 3:
                try:
                    arcpy.management.SplitRaster(
                        in_raster=self.inAscii, out_folder=self.other_path, out_base_name=f"{tile_name}_0",
                        split_method="POLYGON_FEATURES",
                        format="GRID", resampling_type="NEAREST",
                        split_polygon_feature_class=os_selection,
                        clip_type="NONE", template_extent="DEFAULT"
                    )
                    print(f"Successfully split raster for tile: {tile_name} 😊")
                    print(f"Progress: {index}/{len(self.tile_names)} tiles processed.")
                    self.created_rasters.append(out_path)
                    successful_splits += 1
                    break
                except Exception as e:
                    print(f"Couldn't split raster for tile: {tile_name}. Retrying {retry_count + 1}/3... Error: {e}")
                    retry_count += 1
                    time.sleep(1)

            if retry_count == 3:
                print(f"Failed to split raster {tile_name} after 3 attempts.")

        if successful_splits < len(self.tile_names):
            self._cleanup_incomplete_files()
            raise RuntimeError("Not all rasters were created successfully.")
        print("Rasters created successfully! 😊")

    def convert_rasters_to_ascii(self):
        print("Attempting to convert rasters to ASCII...")
        successful_conversions = 0
        for index, raster_path in enumerate(self.created_rasters, start=1):
            new_ascii_name = os.path.basename(raster_path).split("_0")[0] + f"_{self.date}.asc"
            output_asc = os.path.join(self.batch_path, new_ascii_name)
            retry_count = 0

            tile_converted = False  # Flag to track if the current tile was converted

            while retry_count < 3:
                try:
                    arcpy.RasterToASCII_conversion(raster_path, output_asc)
                    self.created_ascii.append(output_asc)
                    print(f"Progress: {index}/{len(self.created_rasters)} tiles processed 😊")
                    successful_conversions += 1
                    tile_converted = True
                    break
                except Exception as e:
                    print(f"Failed to create {output_asc}. Retrying {retry_count + 1}/3... Error: {e}")
                    retry_count += 1
                    time.sleep(1)

            if not tile_converted:
                print(f"Failed to convert raster {raster_path} to ASCII after 3 attempts.")

        if successful_conversions < len(self.created_rasters):
            raise RuntimeError("Not all rasters were successfully converted to ASCII.")
        print("All ASCII files created 😊")

    def clean_up_files(self):
        # ... (no changes needed here)
        print("Moving unnecessary files to cleanup folder...")
        for folder_path in [self.batch_path, self.other_path]:
            for file in os.listdir(folder_path):
                if file.endswith((".asc.xml", ".prj", ".xml", ".ovr", "_0")):
                    try:
                        source_path = os.path.join(folder_path, file)
                        dest_path = os.path.join(self.folder_to_delete, file)
                        shutil.move(source_path, dest_path)
                        print(f"Moved {file} to {self.folder_to_delete}")
                    except Exception as e:
                        print(f"Cannot move {file}. Error: {e}")
        self._delete_cleanup_folder()

    def _cleanup_incomplete_files(self):
        # ... (no changes needed here)
        print("Attempting to clean up any partially created raster files...")
        for path in self.created_rasters:
            try:
                if os.path.isdir(path):
                    shutil.rmtree(path)
                    print(f"Deleted incomplete raster folder: {path}")
            except Exception as e:
                print(f"Failed to delete {path}. Manually delete and rerun. Error: {e}")

    def _delete_cleanup_folder(self):
        # ... (no changes needed here)
        print("Deleting the 'Delete_me' folder....")
        try:
            shutil.rmtree(self.folder_to_delete)
            print("Cleanup folder deleted successfully.")
        except Exception as e:
            print(
                f"Failed to delete the 'Delete_me' folder. Please remove it manually from your downloads folder. Error: {e}")

#from pathlib import Path
## Project root (two levels up from this file)
#PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
#
## Absolute path to shapefile
#ostile_path = PROJECT_ROOT / "dependencies" / "OS_Tiles_All" / "OSTiles_Merged.shp"
#ostile_path = str(ostile_path.resolve())  # ArcPy requires str
#
#split_tile = SplitOSTiles(r"C:\Users\darle\Desktop\Data\Survey_Topo\Phase4\TSW02\6d\6d6D2-4_ParSands\6d6D2-4_20220813tb",
#                 ostile_path)
#split_tile.get_os_tile_names()
#split_tile.split_ascii_into_rasters()
#split_tile.convert_rasters_to_ascii()
#split_tile.clean_up_files()
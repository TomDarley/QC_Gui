import os
import subprocess
import boto3
from botocore.exceptions import NoCredentialsError, ClientError
import re
import time
import tempfile
import os
import rasterio
from rasterio.warp import calculate_default_transform, reproject, Resampling
import pyproj
from rasterio.crs import CRS


class UploadToS3:

    @staticmethod
    def extract_file_paths(qc_folder_paths):

        # a dict to hold the survey unit and its ascii paths if a baseline is found
        sur_unit_tiff_paths = {}

        if not qc_folder_paths:
            print("No QC folder paths provided.")
            return {}

        for folder in qc_folder_paths:

            # 1) get the parent dir this will be one up from the QC folder
            parent_dir = os.path.dirname(folder)

            # 2) extract the tip/tb file name from the parent dir. Is it a baseline survey?
            base_name = os.path.basename(parent_dir)
            date_and_extention = base_name.split("_")[-1]
            if "tb" not in date_and_extention:
                print(f"⚠ No 'tb' found in the file name: {base_name}. Skipping not a baseline survey.")
                continue

            # 3) Grab the survey unit name from the parent dir
            survey_unit = base_name.split("_")[0]
            if not survey_unit:
                print(f"⚠ Could not extract survey unit from folder name: {base_name}. Skipping.")
                continue

            # 4) Extract the ras_1_clipped.tiff file made during auto qc
            for file in os.listdir(folder):
                if file.endswith("ras_1_clipped.tif"):
                    clipped_tiff_file_path = os.path.join(folder, file)
                    break

            if not clipped_tiff_file_path:
                print(f"⚠ No 'ras_1_clipped.tiff' file found in folder: {folder}. Skipping.")
                continue

            # 5) Store the survey unit and its tiff path
            sur_unit_tiff_paths.update({folder: [survey_unit, clipped_tiff_file_path, date_and_extention]})

        return sur_unit_tiff_paths


    def __init__(self, qc_folder_paths):

        self.qc_folder_paths = qc_folder_paths

        self.sur_unit_tiff_path = self.extract_file_paths(self.qc_folder_paths)

        self.current_survey_unit = None

        self.failed_uploads = {}

    def run_upload(self):
        for folder, (sur_unit, tiff_path,date_and_extention) in self.sur_unit_tiff_path.items():
            print(f"Processing Survey Unit: {sur_unit}, ASCII Path: {tiff_path}")
            self.current_survey_unit  = sur_unit
            failed_results = self.reproject_and_compress(sur_unit, tiff_path,date_and_extention )
            if not failed_results:
                print("Successfully processed all files.")
                return {}
            else:
                print(f"❌ Failed to process {sur_unit} from {tiff_path}")
                return failed_results




    def upload_to_s3(self, file_path, bucket_name, s3_path, retries=3, delay=2):
        """Uploads a file to S3 with retries and a check to avoid overwriting
           an existing object. Has exponential backoff on retries.

        Parameters:
            file_path (str): Local file to upload
            bucket_name (str): S3 bucket name
            s3_path (str): Path (key) inside the bucket
            retries (int): Number of upload attempts
            delay (int): Seconds to wait between retries"""

        s3 = boto3.client('s3', region_name='eu-west-2')
        full_key = f"{self.current_survey_unit}/{s3_path}"


        # --- Check if file already exists ---
        try:
            s3.head_object(Bucket=bucket_name, Key=full_key)
            print(f"File already exists in S3: {bucket_name}/{self.current_survey_unit}/{s3_path}")
            return False
        except ClientError as e:
            if e.response['Error']['Code'] != "404":
                print(f"⚠ Error checking object existence: {e}")
                return False
            # Safe to upload if 404

        # --- Upload with retries + exponential backoff ---
        current_delay = delay

        for attempt in range(1, retries + 1):

            try:
                #s3.upload_file(file_path, bucket_name, s3_path)
                print(f"✅ Uploaded {file_path} → s3://{bucket_name}/{s3_path}")
                return True

            except NoCredentialsError:
                print("AWS credentials not available.")
                return False

            except Exception as e:
                print(f"⚠ Attempt {attempt}/{retries} failed: {e}")

                if attempt < retries:
                    print(f"⏳ Retrying in {current_delay}s...")
                    time.sleep(current_delay)
                    current_delay *= 2  # Exponential backoff
                else:
                    print("Upload failed after all retries.")
                    return False

    def convert_and_reproject(self, input_path, output_path, src_crs, dst_crs):
        """
        Reprojects a raster (TIFF or ASC) and applies compression.

        Parameters:
            input_path (str): Path to input raster (.tif or .asc)
            output_path (str): Path to final output GeoTIFF
            src_crs (str): Source CRS (e.g., "EPSG:27700")
            dst_crs (str): Target CRS (e.g., "EPSG:4326")
        """

        # Ensure output folder exists
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        # Step 1: If input is ASC, convert to temporary TIFF first
        ext = os.path.splitext(input_path)[1].lower()
        temp_tiff = None
        if ext == ".asc":
            temp_tiff = os.path.join(
                os.path.dirname(output_path),
                os.path.splitext(os.path.basename(output_path))[0] + "_converted.tif"
            )
            print(f"Converting ASC to TIFF: {temp_tiff}")
            with rasterio.open(input_path) as src:
                profile = src.profile.copy()
                profile.update(driver='GTiff')
                with rasterio.open(temp_tiff, 'w', **profile) as dst:
                    dst.write(src.read())
            input_path = temp_tiff

        # Step 2: Reproject and compress
        print(f"Reprojecting {input_path} -> {output_path}")
        with rasterio.open(input_path) as src:

            nodata = src.nodata  # Get the raster’s nodata value, or set manually
            if nodata is None:
                nodata = -9999  # or another suitable placeholder


            transform, width, height = calculate_default_transform(
                src.crs, dst_crs, src.width, src.height, *src.bounds
            )
            kwargs = src.meta.copy()
            kwargs.update({
                'crs': dst_crs,
                'transform': transform,
                'width': width,
                'height': height,
                'compress': 'DEFLATE',
                'predictor': 2,  # Match -co PREDICTOR=2
                'zlevel': 5,  # Match -co ZLEVEL=5
                'tiled': True,
                'nodata': nodata
            })

            with rasterio.open(output_path, 'w', **kwargs) as dst:
                for i in range(1, src.count + 1):
                    reproject(
                        source=rasterio.band(src, i),
                        destination=rasterio.band(dst, i),
                        src_transform=src.transform,
                        src_crs=src.crs,
                        dst_transform=transform,
                        dst_crs=dst_crs,
                        resampling=Resampling.nearest
                    )

        print(f"Reprojection and compression complete: {output_path}")

        # Step 3: Upload the reprojected and compressed file to S3
        s3_bucket = 'dash-raster-bucket'  # Replace with your S3 bucket name
        s3_file_path = os.path.basename(output_path)  # S3 path within the bucket
        print(s3_file_path)
        self.upload_to_s3(output_path ,s3_bucket, s3_file_path)


    def reproject_and_compress(self, sur_unit ,tiff_path,date_and_extention):

        output_folder =  os.path.join(tempfile.gettempdir(), "reprojected_tiffs", sur_unit)

        # Ensure output folder exists
        os.makedirs(output_folder, exist_ok=True)

        # Make temp output folder for reprojected tiffs
        tiff_out_put_file_name = f"{sur_unit}_{date_and_extention}.tiff"


        output_path = os.path.join(output_folder, f"{tiff_out_put_file_name}")


        # Define source and target CRS (EPSG:27700 is OSGB36 and EPSG:4326 is WGS84)
        src_crs = "EPSG:27700"  # Source CRS (British National Grid)
        dst_crs = "EPSG:4326"  # Target CRS (WGS 84)

        dst_crs = CRS.from_epsg(4326)
        src_crs = CRS.from_epsg(27700)

        # Convert and reproject
        send_result = self.convert_and_reproject(tiff_path, output_path, src_crs, dst_crs)
        if not send_result:
            self.failed_uploads.update({sur_unit: tiff_path})
            print(f"❌ Failed to process {sur_unit} from {tiff_path}")


        return self.failed_uploads
        print(f"Processed {sur_unit, tiff_path} into {output_path}")


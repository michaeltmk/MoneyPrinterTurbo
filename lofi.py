import os
import boto3
from fastapi import HTTPException, FastAPI
from pydantic import BaseModel
import subprocess
import shutil



TEMP_DIR = "./temp"
os.makedirs(TEMP_DIR, exist_ok=True)

# AWS S3 Client
s3 = boto3.client(
    "s3",
    aws_access_key_id=os.getenv('access_key_id'),
    aws_secret_access_key=os.getenv('access_key_token'),
)

app = FastAPI()

@app.get("/health")
def health_check():
    return {"status": "ok"}


def generate_lofi_video_function(image_bucket: str, audio_bucket: str, video_length: int):
    image_path = os.path.join(TEMP_DIR, "data.png")

    # Step 1: Download the image from S3
    s3.download_file(image_bucket, "data", image_path)
    print(f"Downloaded image: {image_path}")

    # Step 2: List and download all audio files from the bucket
    audio_files = []
    response = s3.list_objects_v2(Bucket=audio_bucket)

    if "Contents" not in response:
        raise HTTPException(status_code=404, detail="No audio files found in the bucket")

    for obj in response["Contents"]:
        audio_key = obj["Key"]
        local_audio_path = os.path.join(TEMP_DIR, audio_key.replace("/", "_"))
        s3.download_file(audio_bucket, audio_key, local_audio_path)
        audio_files.append(local_audio_path)
        print(f"Downloaded audio: {local_audio_path}")

    if not audio_files:
        raise HTTPException(status_code=400, detail="No audio files found")

    # Step 3: Write the audio file paths to a text file with absolute paths
    audio_list_path = os.path.join(TEMP_DIR, "audio_files.txt")
    with open(audio_list_path, "w") as f:
        for audio in audio_files:
            f.write(f"file '{os.path.abspath(audio)}'\n")  # Use absolute path to avoid path issues

    # Step 4: Merge all audio files using ffmpeg
    merged_audio_path = os.path.join(TEMP_DIR, "merged_audio.wav")
    subprocess.run(["ffmpeg", "-f", "concat", "-safe", "0", "-i", audio_list_path, "-c", "copy", merged_audio_path], check=True)

    # Step 4: Create the video with the image (1 hour long)
    video_output_path = os.path.join(TEMP_DIR, "image_video.mp4")
    subprocess.run([
        "ffmpeg", "-loop", "1", "-framerate", "1", "-t", video_length,
        "-i", image_path, "-c:v", "libx264", "-pix_fmt", "yuv420p",
        video_output_path
    ], check=True)
    print(f"Created video: {video_output_path}")

    # Step 5: Loop the audio to match the video length and combine
    final_video_path = os.path.join(TEMP_DIR, "final_video.mp4")
    subprocess.run([
        "ffmpeg", "-i", video_output_path, "-stream_loop", "-1",
        "-i", merged_audio_path, "-shortest", "-map", "0:v", "-map", "1:a",
        "-c", "copy", final_video_path
    ], check=True)
    print(f"Final video created: {final_video_path}")

    return {"message": "Video generated successfully", "video_path": final_video_path}



def upload_video_to_s3(bucket_name, final_video_path):
    try:
        # Define the S3 bucket and object name

        s3_key = os.path.basename(final_video_path)  # Extract filename from the path

        # Upload the file to S3
        s3.upload_file(final_video_path, bucket_name, s3_key)
        print(f"Video uploaded to S3: s3://{bucket_name}/{s3_key}")

    except Exception as e:
        print(f"Error uploading video to S3: {str(e)}")
        raise HTTPException(status_code=500, detail="Error uploading video to S3")

def clear_temp_folder(temp_directory):
    try:
        if os.path.exists(temp_directory):
            shutil.rmtree(temp_directory)  # Delete the entire temp folder
            os.makedirs(temp_directory, exist_ok=True)  # Recreate the folder to keep it available for new files
            print(f"Temp folder cleared: {temp_directory}")
        else:
            print(f"Temp folder does not exist: {temp_directory}")
    except Exception as e:
        print(f"Error clearing temp folder: {str(e)}")


class LofiVideoRequest(BaseModel):
    audio_bucket: str
    image_bucket: str
    final_video_bucket_name: str
    video_length: int

@app.post("/generate-lofi-video/")
def generate_lofi_video(request: LofiVideoRequest):
    try:

        # Generate the video
        result = generate_lofi_video_function(request.image_bucket, request.audio_bucket, str(request.video_length))
        video_path = result.get("video_path")

        # Clear temp folder
        clear_temp_folder(TEMP_DIR)

        return {"message": "Lofi video generation complete", "upload_result": upload_result}

    except Exception as e:
        print(f"Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
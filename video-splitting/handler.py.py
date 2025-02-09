import os
import subprocess
import math
import boto3
import json
from botocore.exceptions import BotoCoreError, ClientError

session = boto3.Session(
        aws_access_key_id='',
        aws_secret_access_key=''
    )
s3_client = session.client('s3')
bucket_name = "1230036628-input"
dest_bucket_name = "1230036628-stage-1"
lambda_client = session.client('lambda')

def video_splitting_cmdline(video_filename):
    print("Start video splitting, filename : ",video_filename)
    filename = os.path.basename(video_filename)
    image_name = os.path.splitext(filename)[0]
    outdir = os.path.join("/tmp", image_name)
    output_dir = outdir
    if not os.path.exists(outdir):
        os.makedirs(outdir)

    #split_cmd = '/usr/bin/ffmpeg -ss 0 -r 1 -i ' +video_filename+ ' -vf fps=1/10 -start_number 0 -vframes 10 ' + outdir + "/" + 'output-%02d.jpg -y'
    #split_cmd = '/usr/bin/ffmpeg -ss 0 -r 1 -i ' +video_filename+ ' -vf fps=1/1 -start_number 0 -vframes 1 ' + outdir + "/" + 'output-%02d.jpg -y'
    split_cmd = '/usr/bin/ffmpeg -ss 0 -r 1 -i ' +video_filename+ ' -vf fps=1/1 -start_number 0 -vframes 1 ' + outdir + "/" + image_name + '.jpg -y' 
    try:
        subprocess.check_call(split_cmd, shell=True)
    except subprocess.CalledProcessError as e:
        print(e.returncode)
        print(e.output)

    fps_cmd = 'ffmpeg -i ' + video_filename + ' 2>&1 | sed -n "s/.*, \\(.*\\) fp.*/\\1/p"'
    fps = subprocess.check_output(fps_cmd, shell=True).decode("utf-8").rstrip("\n")
    fps = math.ceil(float(fps))
    return outdir

def upload_frames_to_s3(frames_dir, dest_bucket_name, frame_file=''):
    if frame_file and frame_file.endswith(".jpg"):
        s3_key = frame_file
        s3_client.upload_file(os.path.join(frames_dir, frame_file), dest_bucket_name, s3_key)


def handler(event, context):
    for rec in event['Records']:
      try:
          # Get the bucket and key where the video was uploaded
          object_key = rec['s3']['object']['key']
  
          download_video_file_path = f"/tmp/{os.path.basename(object_key)}" # this is the download path
          # Download video from S3 to Lambda's temporary storage
          try:
              s3_client.download_file(bucket_name, object_key, download_video_file_path)
              print("File successfully downloaded")
          except (BotoCoreError, ClientError) as error:
              print("Failed to download file:", error)
  
          # Split the video into frames
          frames_dir = video_splitting_cmdline(download_video_file_path)
  
          if frames_dir:
              # Upload frames to S3 bucket
              file=f"{os.path.splitext(os.path.basename(object_key))[0]}"
              frame_file = file + ".jpg"
              upload_frames_to_s3(frames_dir, dest_bucket_name, frame_file)
              
              payload_data = {
                'processed_image': frame_file
              }

              # Convert the payload data to a JSON-formatted string
              payload_json = json.dumps(payload_data)
              
              # Invoke the Lambda function and pass the payload
              response = lambda_client.invoke(
                  FunctionName='face-recognition',
                  InvocationType='Event',  # Asynchronous invocation
                  Payload=payload_json
              )
  
              print("Video split and frames uploaded successfully.")
          else:
              print("Failed to split the video.")
      except Exception as e:
          print(f"An error occurred: {str(e)}")



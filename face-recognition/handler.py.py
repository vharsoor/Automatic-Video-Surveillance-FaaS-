
import os
import cv2
import json
from PIL import Image, ImageDraw, ImageFont
from facenet_pytorch import MTCNN, InceptionResnetV1
from shutil import rmtree
import numpy as np
import torch
import boto3

os.environ['TORCH_HOME'] = '/tmp'

mtcnn = MTCNN(image_size=240, margin=0, min_face_size=20) # initializing mtcnn for face detection
resnet = InceptionResnetV1(pretrained='vggface2').eval() # initializing resnet for face img to embeding conversion

session = boto3.Session(
        aws_access_key_id='',
        aws_secret_access_key=''
    )
s3 = session.client('s3')
input_bucket_name = "1230036628-stage-1"
output_bucket = "1230036628-output"
data_bucket = "1230036628-data"

def face_recognition_function(key_path):
    # Face extraction
    img = cv2.imread(key_path, cv2.IMREAD_COLOR)

    # Face recognition
    key = os.path.splitext(os.path.basename(key_path))[0].split(".")[0]
    img = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
    face, prob = mtcnn(img, return_prob=True, save_path=None)
    s3.download_file(data_bucket, "data.pt", "/tmp/data.pt")
    saved_data = torch.load('/tmp/data.pt')  # loading data.pt file
    if face != None:
        emb = resnet(face.unsqueeze(0)).detach()  # detech is to make required gradient false
        embedding_list = saved_data[0]  # getting embedding data
        name_list = saved_data[1]  # getting list of names
        dist_list = []  # list of matched distances, minimum distance is used to identify the person
        for idx, emb_db in enumerate(embedding_list):
            dist = torch.dist(emb, emb_db).item()
            dist_list.append(dist)
        idx_min = dist_list.index(min(dist_list))

        # Save the result name in a file
        with open("/tmp/" + key + ".txt", 'w+') as f:
            f.write(name_list[idx_min])
        return name_list[idx_min]
    else:
        print(f"No face is detected")
    return


def handler(event, context):
    processed_image = event['processed_image']
    print("frame : ",processed_image)
    local_image_dir = f"/tmp"
    local_file_path = os.path.join(local_image_dir, processed_image)
    # Download image from S3
    s3.download_file(input_bucket_name, processed_image, local_file_path)
    
    filename=processed_image
    if filename.endswith(".jpg"):
        local_image_path = f"{local_image_dir}/{filename}"
        
        # Perform face recognition
        recognized_person = face_recognition_function(local_image_path)
        print("recognized_person = ",recognized_person)
        if recognized_person:
            output_file_name = os.path.splitext(filename)[0] + '.txt'
            output_file_path = f"/tmp/{output_file_name}"
            with open(output_file_path, 'w') as f:
                f.write(recognized_person)
            
            # Upload result to output bucket
            s3.upload_file(output_file_path, output_bucket, output_file_name)
    
    return {
        'statusCode': 200,
        'body': 'Face recognition completed.'
    }


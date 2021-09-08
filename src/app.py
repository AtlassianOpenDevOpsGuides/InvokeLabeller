import boto3
import botocore
import json
import os


def get_file_from_s3(image_token, runtime_region, aws_account_id):
  bucket_name = f'open-devops-images-{runtime_region}-{aws_account_id}'
  
  s3 = boto3.resource('s3')

  try:
    s3.Bucket(bucket_name).download_file(image_token, f'/tmp/{image_token}')
  except botocore.exceptions.ClientError as e:
    if e.response['Error']['Code'] == '404':
      print('the object does not exist.')
    return False
  return True


def query_sagemaker_model(image_token, runtime_region):
  s3_bucket = f'jumpstart-cache-prod-{runtime_region}'
  key_prefix = 'inference-notebook-assets'
  s3 = boto3.client('s3')

  def download_from_s3(key_filenames):
    for key_filename in key_filenames:
        s3.download_file(s3_bucket, f'{key_prefix}/{key_filename}', f'/tmp/{key_filename}')

  ImageNetLabels = 'ImageNetLabels.txt'
  download_from_s3(key_filenames=[ImageNetLabels])

  images = {}
  with open(f'/tmp/{image_token}', 'rb') as file: images[image_token] = file.read()
  with open(f'/tmp/{ImageNetLabels}', 'r') as file: class_id_to_label = file.read().splitlines()

  def query_endpoint(img):

    endpoint_name = 'jumpstart-dft-image-labeller-endpoint'
    client = boto3.client(service_name='runtime.sagemaker', region_name='us-west-1')
    response = client.invoke_endpoint(EndpointName=endpoint_name, ContentType='application/x-image', Body=img)
    model_predictions = json.loads(response['Body'].read())['predictions'][0]
    return model_predictions

  top5_class_labels = None

  for filename, img in images.items():
    model_predictions = query_endpoint(img)
    top5_prediction_ids = sorted(range(len(model_predictions)), key=lambda index: model_predictions[index], reverse=True)[:5]
    top5_class_labels = ', '.join([class_id_to_label[id] for id in top5_prediction_ids])

  return top5_class_labels


def update_dynamodb_tuple(image_token, model_predictions, runtime_region):
  dynamodb = boto3.resource('dynamodb', region_name=runtime_region)
  table = dynamodb.Table('ImageLabels')

  response = table.update_item(
        Key={
            'Id': image_token
        },
        UpdateExpression='set Label=:l',
        ExpressionAttributeValues={
            ':l': model_predictions
        },
        ReturnValues='UPDATED_NEW'
    )

  return response


def lambda_handler(event, context):
  runtime_region = os.environ['AWS_REGION']
  aws_account_id = context.invoked_function_arn.split(":")[4]

  for index, record in enumerate(event['Records']):
    if record['eventName'] == 'INSERT':
      image_token = record['dynamodb']['Keys']['Id']['S']

      fileDownloaded = get_file_from_s3(image_token, runtime_region, aws_account_id)

      if fileDownloaded:
        model_predictions = query_sagemaker_model(image_token, runtime_region)
  
        update_dynamodb_tuple(image_token, model_predictions, runtime_region)

import os

import boto3
from moto import mock_s3
from moto import mock_dynamodb2

from src import app


@mock_s3
def test_get_file_from_s3():
    runtime_region = 'us-east-1'
    aws_account_id = '1234567890'
    bucket_name = f'open-devops-images-{runtime_region}-{aws_account_id}'
    file_name = 'asdf1234.txt'

    conn = boto3.resource('s3', region_name=runtime_region)
    conn.create_bucket(Bucket=bucket_name)

    s3 = boto3.client('s3', region_name='us-east-1')
    s3.put_object(Bucket=bucket_name, Key=file_name, Body='')

    app.get_file_from_s3(file_name, runtime_region, aws_account_id)

    assert os.path.isfile(f'/tmp/{file_name}')


@mock_dynamodb2
def test_update_dynamodb_tuple():
    runtime_region = 'us-east-1'
    table_name = 'ImageLabels'

    conn = boto3.client(
        'dynamodb',
        region_name=runtime_region
    )

    conn.create_table(
        TableName=table_name,
        KeySchema=[{'AttributeName': 'Id', 'KeyType': 'HASH'}],
        AttributeDefinitions=[{'AttributeName': 'Id', 'AttributeType': 'S'}],
        ProvisionedThroughput={'ReadCapacityUnits': 1, 'WriteCapacityUnits': 1},
    )

    conn.put_item(
        TableName=table_name,
        Item={
            'Id': {'S': '1234'},
            'Label': {'S': 'cat'},
        },
    )

    response = app.update_dynamodb_tuple('1234', 'dog', runtime_region)

    assert response['Attributes']['Label'] == 'dog'

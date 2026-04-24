from typing import List
from botocore.exceptions import ClientError
from dotenv import load_dotenv
from botocore.client import Config
from boto3.session import Session
import os

PREFIX = "cdms/umn/slac/idx/"


def get_aws_bucket(verify=True):
    """
    Load AWS bucket given config
    """
    load_dotenv()

    config = Config(signature_version="s3v4")
    endpoint_url = os.getenv("ENDPOINT_URL")
    bucket_name = os.getenv("BUCKET_NAME")
    aws_access_key_id = os.getenv("AWS_ACCESS_KEY_ID")
    aws_secret_access_key = os.getenv("AWS_SECRET_ACCESS_KEY")

    bucket = (
        Session()
        .resource(
            "s3",
            endpoint_url=endpoint_url,
            config=config,
            verify=verify,
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
        )
        .Bucket(bucket_name)
    )
    return bucket


def check_if_key_exists(key: str, verify: bool) -> bool:
    """
    Check if a given key exists in the bucket
    ----
    Return
    bool: True if the key is in the bucket, False otherwise
    """
    if key == "":
        return False

    s3 = get_aws_bucket(verify)
    try:
        obj = s3.Object(key)
        obj.load()
        return True
    except ClientError as e:
        if e.response["Error"]["Code"] == "404":
            return False
        # other error
        return False


def sort_mid_files() -> List[str]:
    mid_files = []
    with open("./uploaded_files.txt") as f:
        for line in f:
            mid_files.append(line.strip())
    sorted_files = sorted(
        mid_files, key=lambda s: (int(s.split("_")[1]), s.split("_")[2])
    )
    return sorted_files


def writesorted():
    files = sort_mid_files()

    with open("sorted.txt", "w") as f:
        for file in files:
            f.write(f"{file}\n")
        f.close()


if __name__ == "__main__":
    writesorted()
    pass

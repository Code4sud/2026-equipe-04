"""Stockage des conversations dans un bucket S3 (SeaweedFS en Docker)."""
from __future__ import annotations

import json
import uuid

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from ..errors import StorageError
from ..models import iso, utcnow

SCHEMA_VERSION = 1


def transcript_key(youth_id: uuid.UUID, conversation_id: uuid.UUID) -> str:
    return f"youths/{youth_id}/{conversation_id}.json"


def new_transcript(youth_id: uuid.UUID, conversation_id: uuid.UUID) -> dict:
    return {
        "schema": SCHEMA_VERSION,
        "conversation_id": str(conversation_id),
        "youth_id": str(youth_id),
        "messages": [],
    }


def new_message(role: str, content: str, flags: list[str] | None = None) -> dict:
    return {
        "id": str(uuid.uuid4()),
        "role": role,
        "content": content,
        "created_at": iso(utcnow()),
        "flags": flags or [],
    }


class S3TranscriptStore:
    def __init__(self, endpoint: str, access_key: str, secret_key: str, bucket: str, region: str):
        self.bucket = bucket
        self._client = boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region,
            config=Config(
                signature_version="s3v4",
                s3={"addressing_style": "path"},
                connect_timeout=3,
                read_timeout=15,
                retries={"max_attempts": 2, "mode": "standard"},
                # Les passerelles S3 compatibles ne gèrent pas toutes les sommes CRC récentes.
                request_checksum_calculation="when_required",
                response_checksum_validation="when_required",
            ),
        )

    def load(self, key: str) -> dict:
        try:
            response = self._client.get_object(Bucket=self.bucket, Key=key)
            return json.loads(response["Body"].read())
        except (ClientError, BotoCoreError, ValueError) as error:
            raise StorageError(f"lecture de {key} impossible : {error}") from error

    def save(self, key: str, transcript: dict) -> None:
        body = json.dumps(transcript, ensure_ascii=False).encode("utf-8")
        try:
            try:
                self._put(key, body)
            except ClientError as error:
                if error.response.get("Error", {}).get("Code") != "NoSuchBucket":
                    raise
                self.ensure_bucket()
                self._put(key, body)
        except (ClientError, BotoCoreError) as error:
            raise StorageError(f"écriture de {key} impossible : {error}") from error

    def ensure_bucket(self) -> None:
        try:
            self._client.create_bucket(Bucket=self.bucket)
        except ClientError as error:
            code = error.response.get("Error", {}).get("Code")
            if code not in {"BucketAlreadyOwnedByYou", "BucketAlreadyExists"}:
                raise

    def ping(self) -> bool:
        try:
            self.ensure_bucket()
            self._client.head_bucket(Bucket=self.bucket)
            return True
        except (ClientError, BotoCoreError):
            return False

    def _put(self, key: str, body: bytes) -> None:
        self._client.put_object(
            Bucket=self.bucket, Key=key, Body=body, ContentType="application/json"
        )

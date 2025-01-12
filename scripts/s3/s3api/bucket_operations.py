#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# Copyright (c) 2020 Seagate Technology LLC and/or its Affiliates
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.
# For any questions about this software or licensing,
# please email opensource@seagate.com or cortx-questions@seagate.com.
#
"""S3 bucket operation workload for io stability."""

import logging
import os
import random
import time
from datetime import datetime, timedelta
from typing import Union

from botocore.exceptions import ClientError

from src.libs.s3api.s3_bucket_ops import S3Bucket
from src.libs.s3api.s3_object_ops import S3Object

LOGGER = logging.getLogger(__name__)


# pylint: disable=too-few-public-methods, too-many-statements
class TestBucketOps(S3Object, S3Bucket):
    """S3 Bucket Operations class for executing given io stability workload"""

    # pylint: disable=too-many-arguments, too-many-locals, too-many-instance-attributes
    def __init__(self, access_key: str, secret_key: str, endpoint_url: str, test_id: str,
                 use_ssl: str, object_size: Union[int, dict], seed: int,
                 duration: timedelta = None) -> None:
        """
        s3 bucket operations init class.

        :param access_key: access key.
        :param secret_key: secret key.
        :param endpoint_url: endpoint with http or https.
        :param test_id: Test ID string.
        :param use_ssl: To use secure connection.
        :param object_size: Object size to be used for bucket operation
        :param seed: Seed to be used for random data generator
        :param duration: Duration timedelta object, if not given will run for 100 days.
        """
        super().__init__(access_key, secret_key, endpoint_url=endpoint_url, use_ssl=use_ssl)
        random.seed(seed)
        self.object_size = object_size
        self.test_id = test_id
        self.min_duration = 10  # In seconds
        self.object_per_iter = 500
        self.iteration = 1
        if duration:
            self.finish_time = datetime.now() + duration
        else:
            self.finish_time = datetime.now() + timedelta(hours=int(100 * 24))

    async def execute_bucket_workload(self):
        """Execute bucket operations workload for specific duration."""
        while True:
            LOGGER.info("Iteration %s is started for %s...", self.iteration, self.test_id)
            try:
                if isinstance(self.object_size, dict):
                    file_size = random.randrange(self.object_size["start"], self.object_size["end"])
                else:
                    file_size = self.object_size
                bucket_name = f'bucket-op-{self.test_id}-{time.perf_counter_ns()}'.lower()
                LOGGER.info("Create bucket %s", bucket_name)
                await self.create_bucket(bucket_name)
                LOGGER.info("Upload %s objects to bucket %s", self.object_per_iter, bucket_name)
                for _ in range(0, self.object_per_iter):
                    file_name = f'object-bucket-op-{time.perf_counter_ns()}'
                    LOGGER.info("Object '%s', object size %s Kib", file_name, file_size / 1024)
                    with open(file_name, 'wb') as f_out:
                        f_out.write(os.urandom(file_size))
                    await self.upload_object(bucket_name, file_name, file_path=file_name)
                    LOGGER.info("'s3://%s/%s' uploaded successfully.", bucket_name, file_name)
                    LOGGER.info("Delete generated file")
                    os.remove(file_name)
                LOGGER.info("List all buckets")
                await self.list_buckets()
                LOGGER.info("List objects of created %s bucket", bucket_name)
                await self.list_objects(bucket_name)
                LOGGER.info("Perform Head bucket")
                await self.head_bucket(bucket_name)
                LOGGER.info("Delete bucket %s with all objects in it.", bucket_name)
                await self.delete_bucket(bucket_name, True)
            except (ClientError, IOError, AssertionError) as err:
                LOGGER.exception(err)
                raise err
            timedelta_v = (self.finish_time - datetime.now())
            timedelta_sec = timedelta_v.total_seconds()
            if timedelta_sec < self.min_duration:
                return True, "Bucket operation execution completed successfully."
            LOGGER.info("Iteration %s is completed of %s...", self.iteration, self.test_id)
            self.iteration += 1

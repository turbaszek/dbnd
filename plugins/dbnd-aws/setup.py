from os import path

import setuptools

from setuptools.config import read_configuration


BASE_PATH = path.dirname(__file__)
CFG_PATH = path.join(BASE_PATH, "setup.cfg")

config = read_configuration(CFG_PATH)
version = config["metadata"]["version"]

setuptools.setup(
    name="dbnd-aws",
    package_dir={"": "src"},
    install_requires=[
        "dbnd==" + version,
        # otherwise airflow dependencies are broken
        "httplib2>=0.9.2",
        "boto3",
        "botocore",
        "s3fs",
    ],
    extras_require=dict(tests=["awscli"]),
    entry_points={"dbnd": ["dbnd-aws = dbnd_aws._plugin"]},
)

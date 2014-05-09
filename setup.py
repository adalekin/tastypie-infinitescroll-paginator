from setuptools import setup, find_packages

setup(
    name="tastypie-infinitescroll-paginator",
    version="0.0.1",
    packages=find_packages(),
    package_data={
        'infinitescroll_paginator': [
            '*.*',
        ]
    },
    include_package_data=True,
    long_description="Infinite scroll paginator for django-tastypie.",
)

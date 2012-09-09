#!/bin/bash

coverage run --source . testsuite.py

coverage report -m

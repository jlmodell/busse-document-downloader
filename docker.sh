#!/bin/bash
git pull && docker-compose stop && docker-compose up -d --build --remove-orphans

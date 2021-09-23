FROM python:3.6

RUN apt-get update && apt-get install -y postgresql-client

WORKDIR /epds
COPY requirements.txt .
RUN pip install -r requirements.txt

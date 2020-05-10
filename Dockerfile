# base image
FROM python:3.8-slim-buster

# set working directory
RUN mkdir -p /usr/src/app
WORKDIR /usr/src/app

RUN apt update \
  && apt install -y libglib2.0-0 libsm6 libxext6 libxrender1 ghostscript\
  && rm -rf /var/lib/apt/lists/*


# add requirements (to leverage Docker cache)
ADD ./requirements.txt /usr/src/app/requirements.txt

# install requirements
RUN pip install -r requirements.txt

# copy project
COPY . /usr/src/app

EXPOSE 5000
CMD ["python", "main.py"]

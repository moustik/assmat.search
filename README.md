# assmat.prepare

## Usage

### CLI
```sh
pip install -r requirements
python main.py -i document.pdf -o document.csv -s map.html
```

### Application

```sh
pip install -r requirements
CACHE_DIR=. python main.py
```

### Docker

```sh
docker build . -t assmat.search
docker run --rm -p 5000:5000 -e CACHE_DIR=/cache -v /cache assmat.search
```

## Requirements

### pip & virtualenv

    - [pip](https://github.com/pypa/get-pip)
    - [virtualenv](https://virtualenv.pypa.io/en/stable/installation.html)

### OpenCV

Debian : `libglib2.0-0 libsm6 libxext6 libxrender1 ghostscript`

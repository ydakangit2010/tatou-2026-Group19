# tatou
A web platform for pdf watermarking. This project is intended for pedagogical use, and contain security vulnerabilities. Do not deploy on an open network.

## Instructions

The following instructions are meant for a bash terminal on a Linux machine. If you are using something else, you will need to adapt them.

To clone the repo, you can simply run:

```bash
git clone https://github.com/nharrand/tatou-2026.git
```

Note that you should probably fork the repo and clone your own repo.


### Run python unit tests

```bash
cd tatou/server

# Create a python virtual environement
python3 -m venv .venv

# Activate your virtual environement
. .venv/bin/activate

# Install the necessary dependencies
python -m pip install -e ".[dev]"

# Run the unit tests
python -m pytest
```

### Deploy

From the root of the directory:

```bash
# Create a file to set environement variables like passwords.
cp sample.env .env

# Edit .env and pick the passwords you want

# Rebuild the docker image and deploy the containers
docker compose up --build -d

# Monitor logs in realtime 
docker compose logs -f

# Test if the API is up
http -v :5000/healthz

# Open your browser at 127.0.0.1:5000 to check if the website is up.
```

## My watermarking method: ak-metadata

I created a watermarking method called ak-metadata.

It stores the watermark in the PDF metadata, inside the keywords field. The secret is Base64 encoded and protected with HMAC-SHA256 using the key.

The method:
- can add a watermark to a PDF
- can read the secret again with the correct key
- rejects a wrong key
- keeps the existing PDF metadata
- does not use the position value
- works with valid PDFs that have at least one page

Implementation:

server/src/ak_metadata_watermark.py

Tests:

server/test/test_ak_metadata_watermark.py


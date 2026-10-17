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

Note: Some tests use a MariaDB test database and may recreate it.
Run the full test suite only in a properly isolated test environment.
Do not run it against the production database.


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


### API testing

The project contains automated API tests in `server/test/`, including
tests for authentication, access control, uploads and error handling.

To run the basic API health-check test from the project root:

```bash
cd server
SECRET_KEY=local-test-only-key .venv/bin/python -m pytest test/test_api.py -k test_healthz_route
```

### Coverage analysis

We used Coverage.py to measure statement coverage for two Python
modules: `server.py` and `ak_metadata_watermark.py`.

The saved coverage results can be viewed from the `server` directory:

```bash
.venv/bin/python -m coverage report -m
.venv/bin/python -m coverage html
```

Our focused coverage run covered 54% of statements across these
two modules: 88% for `ak_metadata_watermark.py` and 49% for
`server.py`. These results do not represent whole-project coverage.

The HTML coverage report is saved in `server/htmlcov/`.

To reproduce the focused coverage measurement, run the following
from the `server` directory in a correctly configured test environment:

```bash
SECRET_KEY=local-test-only-key .venv/bin/python -m pytest \
  test/test_ak_metadata_watermark.py \
  test/test_authentication.py \
  test/test_access_control.py \
  -q --cov=server --cov=ak_metadata_watermark \
  --cov-report=term-missing --cov-report=html:htmlcov
```

These are focused tests, not the full test suite. The database-dependent
tests require an isolated test database.

### Mutation testing

We use [Cosmic Ray](https://github.com/sixty-north/cosmic-ray) to check whether the
tests notice small faults in `server/src/server.py`. It changes the code one mutant at
a time (for example `or` → `and`, `401` → `402`, a removed route decorator) and runs the
test suite. A mutant that no test notices "survives" and points to a missing check.
The configuration is `server/cosmic-ray.toml`.

Start a throwaway MariaDB for the database tests (the same image CI uses):

```bash
docker run -d --name tatou-test-db -e MARIADB_ROOT_PASSWORD=test-root \
  -p 127.0.0.1:3307:3306 mariadb:11.4
```

Then, from the `server` directory:

```bash
python -m pip install -e ".[dev,mutation]"
export SECRET_KEY=local-test-only-key TEST_DB_REQUIRED=1
cosmic-ray init cosmic-ray.toml session.sqlite
cosmic-ray baseline cosmic-ray.toml
cosmic-ray exec cosmic-ray.toml session.sqlite
cr-report session.sqlite
cr-html session.sqlite > mutation-report.html
```

A single-process run of all ~860 mutants takes a few hours.

Cosmic Ray does not mutate string literals, so it cannot change the SQL ownership
filters (`ownerid = :uid`). Those are covered by the real-database tests in
`server/test/test_access_control_db.py`.

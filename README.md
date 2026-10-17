# tatou
A web platform for pdf watermarking. This project is intended for pedagogical use, and contain security vulnerabilities. Do not deploy on an open network.

## Instructions

The following instructions are meant for a bash terminal on a Linux machine. If you are using something else, you will need to adapt them.

To clone the repo, you can simply run:

```bash
git clone https://github.com/ydakangit2010/tatou-2026-Group19.git
```


### Run python unit tests

```bash
cd tatou-2026-Group19/server

# Create a python virtual environement
python3 -m venv .venv

# Activate your virtual environement
. .venv/bin/activate

# Install the necessary dependencies
python -m pip install -e ".[dev]"

# Run the unit tests
SECRET_KEY=local-test-only-key python -m pytest
```

Note: Some tests use a MariaDB test database and may recreate it.
Run the full test suite only in a properly isolated test environment.
Do not run it against the production database.

Without a test database those tests are skipped. To run them, start a throwaway
MariaDB on `127.0.0.1:3307` (the same image and settings as CI) and make the
database tests required, so they fail instead of being skipped:

```bash
docker run -d --name tatou-test-db -e MARIADB_ROOT_PASSWORD=test-root \
  -p 127.0.0.1:3307:3306 mariadb:11.4

SECRET_KEY=local-test-only-key TEST_DB_REQUIRED=1 python -m pytest
```

The tests create their own database, `tatou_test`, from `db/tatou.sql`, and
refuse to use any database whose name does not end in `_test`.

### API testing

The project contains automated API tests in `server/test/`, including
tests for authentication, access control, uploads and error handling.

To run the basic API health-check test from the project root:

```bash
cd server
SECRET_KEY=local-test-only-key .venv/bin/python -m pytest test/test_api.py -k test_healthz_route
```

### Coverage analysis

We use Coverage.py, through `pytest-cov` (installed with the `dev` extras), to
measure statement coverage of the server code in `server/src/`. From the `server`
directory, with the test database running (see [Run python unit tests](#run-python-unit-tests)):

```bash
SECRET_KEY=local-test-only-key TEST_DB_REQUIRED=1 python -m pytest \
  --cov=src --cov-report=term-missing --cov-report=html:htmlcov
```

The terminal shows the coverage of each file and the lines that did not run.
The HTML report is written to `server/htmlcov/index.html`.

Result of the full suite with the test database (17 October 2026), 72% of all statements:

| File | Coverage |
| --- | --- |
| `server.py` | 80% |
| `jz_watermark.py` | 96% |
| `ak_metadata_watermark.py` | 89% |
| `unsafe_bash_bridge_append_eof.py` | 92% |
| `add_after_eof.py` | 83% |
| `watermarking_method.py` | 80% |
| `watermarking_utils.py` | 46% |
| `watermarking_cli.py` | 0% (command-line tool, not tested) |

### Mutation testing

We use [Cosmic Ray](https://github.com/sixty-north/cosmic-ray) to check whether the
tests notice small faults in `server/src/server.py`. It changes the code one mutant at
a time (for example `or` → `and`, `401` → `402`, a removed route decorator) and runs the
test suite. A mutant that no test notices "survives" and points to a missing check.
The configuration is `server/cosmic-ray.toml`.

Start the test database (see [Run python unit tests](#run-python-unit-tests)), then,
from the `server` directory:

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

### Deploy

The containers read these files from your home directory (see `docker-compose.yml`):

- `~/server_pub.asc` and `~/server_priv.asc`: the server's OpenPGP key pair for RMAP. Never commit the private key.
- `~/rmap_client_keys/`: the course-provided public keys of the groups allowed to use RMAP, one `Group_XX.asc` file per group.
- `~/Group_19.pdf`: the confidential PDF that RMAP hands out, watermarked for each group.
- `~/flag2`: flag 2, mounted read-only at `/app/flag`.

From the root of the directory:

```bash
# Create a file to set environement variables like passwords.
cp sample.env .env

# Edit .env: pick the database passwords and a long random SECRET_KEY.
# Leave RMAP_SERVER_KEY_PASSPHRASE empty unless the server key has a passphrase.

# Rebuild the docker image and deploy the containers
docker compose up --build -d

# Monitor logs in realtime 
docker compose logs -f

# Test if the API is up; "db_connected" should be true
curl -s http://127.0.0.1:5000/healthz

# Open your browser at 127.0.0.1:5000 to check if the website is up.
```

RMAP serves the document named `Group_19.pdf` owned by the user `rmap_group19`.
After the first deployment, create that account and upload `Group_19.pdf` with it once.

## Watermarking methods

### ak-metadata (Akanksha Yadav)

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

### jz-dotgrid (Josef Žemlička)

jz-dotgrid hides the secret as faint grey dots in the page margins, so it stays in the
page content when a PDF is re-saved, has its metadata stripped, or is turned into an image.

The method:
- encodes each bit as a pair of neighbouring spots and only compares which one is darker, so a tinted, darkened or rasterised page can still be read
- protects the secret with an HMAC (a wrong key is rejected) and encrypts it with a keystream derived from the key, using only the standard library
- repeats the frame across the margins and reads it back by majority vote
- accepts secrets up to 64 bytes and ignores the position value
- does not survive very low resolution, heavily compressed re-renders, or whitening of light greys

RMAP copies carry both jz-dotgrid and ak-metadata, keyed with
`HMAC(SECRET_KEY, "rmap-watermark:" + link)`, so the link alone cannot read or forge them.

Implementation:

server/src/jz_watermark.py

Tests:

server/test/test_jz_watermark.py, server/test/test_combined_watermark.py

# Tatou API Documentation

---

# Routes

- [create-user](#create-user) — **POST** `/api/create-user`
- [create-watermark](#create-watermark)
  - **POST** `/api/create-watermark/<int:document_id>`
  - **POST** `/api/create-watermark`
- [delete-document](#delete-document)
  - **DELETE** `/api/delete-document/<document_id>`
  - **DELETE, POST** `/api/delete-document`
- [get-document](#get-document)
  - **GET** `/api/get-document/<int:document_id>`
  - **GET** `/api/get-document`
- [get-version](#get-version) — **GET** `/api/get-version/<link>`
- [get-watermarking_methods](#get-watermarking-methods) — **GET** `/api/get-watermarking-methods`
- [healthz](#healthz) — **GET** `/healthz`
- [list-all-versions](#list-all-versions) — **GET** `/api/list-all-versions`
- [list-documents](#list-documents) — **GET** `/api/list-documents`
- [list-versions](#list-versions)
  - **GET** `/api/list-versions/<int:document_id>`
  - **GET** `/api/list-versions`
- [login](#login) — **POST** `/api/login`
- [read-watermark](#read-watermark)
  - **POST** `/api/read-watermark/<int:document_id>`
  - **POST** `/api/read-watermark`
- [upload-document](#upload-document) — **POST** `/api/upload-document`
- [rmap-initiate](#rmap-initiate) — **POST** `/api/rmap-initiate`
- [rmap-get-link](#rmap-get-link) — **POST** `/api/rmap-get-link`


# Conventions

These rules apply to every route unless its own section says otherwise.

**Authentication**
 * Routes marked "Requires authentication" MUST be called with the header `Authorization: Bearer <token>`, using a token from [login](#login).
 * A missing, invalid or expired token MUST be answered with `401`.

**Ownership**
 * A route that reads or changes documents, versions or watermarks MUST only act on data owned by the authenticated user.
 * Ownership MUST be decided by the user's numeric id, taken from the signed token. It MUST NOT be decided by the login name or by any value in the request, such as an `ownerid` form field.
 * A request for another user's document MUST be answered exactly like a request for a document that does not exist (`404 {"error": "document not found"}`), so that it does not reveal whether the document exists.
 * List routes MUST return an empty list, not an error, when the user owns nothing matching.

**Errors**
 * Errors MUST be returned as JSON of the form `{"error": <string>}`.
 * Error messages MUST NOT contain internal details such as exception text, SQL statements, file paths or library messages. Those details are written to the server log instead.

| Status | Meaning |
| --- | --- |
| `400` | Missing or invalid parameters |
| `401` | Missing, invalid or expired token, or wrong credentials |
| `404` | The resource does not exist or belongs to another user |
| `409` | The email or login is already registered |
| `410` | The database entry exists but its file is missing on disk |
| `413` | The request body is larger than 20 MB |
| `429` | Too many attempts; the response carries a `Retry-After` header in seconds |
| `503` | The database could not be reached or rejected the operation |

**Limits**
 * Request bodies, including uploads, MUST NOT exceed 20 MB. Larger requests MUST be answered with `413 {"error": "file too large (max 20 MB)"}`.


## healthz

**Path**
`GET /healthz`

**Description**  
This endpoint checks the health of the server and confirms it is running.

**Parameters**  
_None_

**Return**
```json
{
  "message": <string>,
  "db_connected": <bool>
}
```

**Specification**
 * The healthz endpoint MUST be accessible without authentication.
 * The response MUST always contain a "message" field of type string.
 * `db_connected` reports whether the server can currently reach the database.
 
## create-user
 
**Path**
`POST /api/create-user`

**Description**  
This endpoint creates a new user account in the system.

**Parameters**
```json
{
  "login": <string>,
  "password": <string>,
  "email": <email>
}
```

**Return**
```json
{
  "id": <int>,
  "login": <string>,
  "email": <email>
}
```


**Specification**
 * The create-user endpoint MUST validate that username, password, and email are provided.
 * The response MUST include a unique id along with the created username and email.
 * Emails MUST be unique. They are stored in lower case.
 * Logins MUST be unique, compared without regard to letter case (`Alice` and `alice` are the same login).
 * The password MUST be 15 to 128 characters long. Otherwise the response MUST be `400 {"error": "password must be 15 to 128 characters long"}`.
 * If the email or the login is already registered, the response MUST be `409 {"error": "email or login already exists"}`. The message MUST NOT say which of the two is taken, so that the route reveals as little as possible about existing accounts.
 * The endpoint MUST be limited to 10 requests per minute per client IP address; further requests get `429`.
 * Passwords MUST only be stored as salted hashes.


## login

**Path**
`POST /api/login`

**Description**  
This endpoint authenticates a user with their credentials and returns a session token.

**Parameters**
```json
{
  "email": <string>,
  "password": <string>
}
```

**Return**
```json
{
  "token": <string>,
  "token_type": "bearer",
  "expires_in": <int>
}
```

**Specification**
 * The login endpoint MUST reject requests missing email or password.
 * The response MUST include a token string and its expiration date as an integer Time To Live in seconds.
 * An unknown email and a wrong password MUST get the same response, `401 {"error": "invalid credentials"}`, and MUST take about the same time to answer, so that neither the message nor the response time reveals which emails are registered.
 * The endpoint MUST be limited to 10 requests per minute per client IP address; further requests get `429`.
 
## upload-document

**Path**
`POST /api/upload-document`

**Description**  
This endpoint uploads a PDF document to the server and registers its metadata.

**Parameters** (as `multipart/form-data`)
```json
{
  "file": <pdf file>,
  "name": <string>
}
```

**Return**
```json
{
  "id": <string>,
  "name": <string>,
  "creation": <date ISO 8601>,
  "sha256": <string>,
  "size": <int>
}
```

**Specification**
 * Requires authentication
 * The upload-pdf endpoint MUST accept only files in PDF format.
 * The uploaded document MUST be owned by the authenticated user. Any owner given in the request MUST be ignored.
 * `name` is optional; the uploaded file's name is used when it is missing.
 * Uploads larger than 20 MB MUST be refused with `413`.
 * The file MUST be stored inside the server's storage directory, in a folder named after the user's numeric id. User-supplied values such as the login or the filename MUST NOT be able to place it anywhere else.

## list-documents

**Path**
`GET /api/list-documents`

**Description**  
This endpoint lists all uploaded PDF documents along with their metadata.

**Parameters**  
_None_

**Return**
```json
{
  "documents": [
    {
      "id": <string>,
      "name": <string>,
      "creation": <date ISO 8601>,
      "sha256": <string>,
      "size": <int>
    }
  ]
}
```

**Specification**
 * Requires authentication
 * The response MUST return all documents of the user.
 * The response MUST NOT include documents of other users.
 
## list-versions

**Description**  
This endpoint lists all watermarked versions of a given PDF document along with their metadata.

**Path**
`GET /api/list-versions`

**Parameters** (as query string: `?id=` or `?documentid=`)
```json
{
  "documentid": <int>
}
```

**Path**
`GET /api/list-versions/<int:document_id>`

**Parameters**  
_None_

**Return**
```json
{
  "versions": [
    {
      "id": <string>,
      "documentid": <string>,
      "link": <string>,
      "intended_for": <string>,
      "secret": <string>,
      "method": <string>
    }
  ]
}
```



**Specification**
 * Requires authentication
 * The response MUST only contain versions of the given document when it is owned by the authenticated user, decided by the user's id (see [Conventions](#conventions)). Otherwise the list MUST be empty.
 * A missing or non-numeric document id MUST be answered with `400`.
 
 
## list-all-versions
 
**Path**
`GET /api/list-all-versions`

**Description**  
This endpoint lists all versions of all PDF documents for the authenticated user stored in the system.

**Parameters**  
_None_

**Return**
```json
{
  "versions": [
    {
      "id": <string>,
      "documentid": <string>,
      "link": <string>,
      "intended_for": <string>,
      "secret": <string>,
      "method": <string>
    }
  ]
}
```

**Specification**
 * Requires authentication
 * The response MUST contain the versions of every document owned by the authenticated user, decided by the user's id, and no others.
 
## get-document
 
**Description**  
This endpoint retrieves a PDF document by fetching a specific one when an `id` is provided.
 
**Path**
`GET /api/get-document`


**Parameters** (as query string: `?id=` or `?documentid=`)
```json
{
  "id": <int>
}
```

**Path**
`GET /api/get-document/<int:document_id>`

**Return**
Inline PDF file in binary format.

**Specification**
 * Requires authentication
 * Only the owner of the document MUST be able to retrieve it. Anyone else MUST get `404 {"error": "document not found"}`.
 * A missing or non-numeric document id MUST be answered with `400`.

## delete-document

**Description**  
This endpoint deletes a document, its file on disk and its watermarked versions.

**Path**
`DELETE /api/delete-document/<document_id>`

**Parameters**  
_None_

**Path**
`DELETE, POST /api/delete-document`

**Parameters** (as query string `?id=` / `?documentid=`, or as JSON body)
```json
{
  "id": <int>
}
```

**Return**
```json
{
  "deleted": true,
  "id": <int>,
  "file_deleted": <bool>,
  "file_missing": <bool>,
  "note": <string or null>
}
```

**Specification**
 * Requires authentication
 * Only the owner of the document MUST be able to delete it. Anyone else MUST get `404 {"error": "document not found"}`, and nothing may be deleted.
 * Deleting a document MUST also delete its watermarked versions.
 * The file MUST only be deleted when its stored path lies inside the server's storage directory.
 * `note` is `null` when everything went well. Otherwise it MUST be one of the fixed texts `"failed to delete file"` or `"document path invalid"`, and MUST NOT contain file paths or exception text.

## get-version

**Description**  
This endpoint retrieves a watermarked version of a document through its secret link. This is how a document owner shares a version with its intended recipient.

**Path**
`GET /api/get-version/<link>`

**Parameters**  
_None_

**Return**
Inline PDF file in binary format.

**Specification**
 * The get-version endpoint MUST be accessible without authentication; knowing the link is what grants access.
 * Links MUST be unguessable: at least 128 bits of randomness, generated with a cryptographically secure random generator. Links from RMAP are the 32-hex session secret described in [rmap-get-link](#rmap-get-link).
 * An unknown link MUST be answered with `404 {"error": "document not found"}`.
 * Each link MUST keep serving the file of its own version, even after further versions of the same document are created for the same recipient.
 
## get-watermarking-methods
 
**Description**  
This endpoint lists all available watermarking methods.
 
**Path**
`GET /api/get-watermarking-methods`


**Parameters**
_None_


**Return**
```json
{
    "count": <int>,
    "methods": [
        {
            "description": <string>,
            "name": <string>
        }
    ]
}
```

**Specification**
 * The endpoint MUST return all methods in `watermarking_utils.METHODS`.
 * The endpoint MUST be accessible without authentication.
 
## read-watermark
 
**Description**  
This endpoint reads information contain in a pdf document's watermark with the provided method.
 
**Path**
`POST /api/read-watermark`

**Parameters**
```json
{
    "method": <string>,
    "position": <string>,
    "key": <string>,
    "id": <int>
}
```
 
**Path**
`POST /api/read-watermark/<int:document_id>`


**Parameters**
```json
{
    "method": <string>,
    "position": <string>,
    "key": <string>
}
```


**Return**
```json
{
    "documentid": <int>,
    "secret": <string>,
    "method": <string>,
    "position": <string>
}
```

**Specification**
 * Requires authentication
 * The endpoint MUST return the secret read in the document.
 * Only the owner of the document MUST be able to read its watermark. Anyone else MUST get `404 {"error": "document not found"}`.
 * `method` and `key` are required; `position` is optional.
 * If the watermark cannot be read (unknown method, wrong key, no watermark), the response MUST be `400 {"error": "could not read watermark"}`.


## create-watermark
 
**Description**  
This endpoint creates a watermarked version of a document for one intended recipient and returns the secret link to it.
 
**Path**
`POST /api/create-watermark`

**Parameters**
```json
{
    "method": <string>,
    "position": <string>,
    "key": <string>,
    "secret": <string>,
    "intended_for": <string>,
    "id": <int>
}
```
 
**Path**
`POST /api/create-watermark/<int:document_id>`


**Parameters**
```json
{
    "method": <string>,
    "position": <string>,
    "key": <string>,
    "secret": <string>,
    "intended_for": <string>
}
```


**Return**
```json
{
    "id": <int>,
    "documentid": <int>,
    "link": <string>,
    "intended_for": <string>,
    "method": <string>,
    "position": <string>,
    "filename": <string>,
    "size": <int>
}
```

**Specification**
 * Requires authentication
 * Only the owner of a document should be able to create watermarked versions of their documents. Anyone else MUST get `404 {"error": "document not found"}`.
 * The document owner MUST be able to list all versions of their documents and their intended recipients
 * `method`, `intended_for`, `secret` and `key` are required; `position` is optional.
 * Every call MUST create a new, separate version with its own file and its own link, even for a recipient who already has a version. Earlier versions MUST NOT be changed.
 * An unknown or unsuitable method MUST be answered with `400 {"error": "watermarking method not applicable"}`.
 * `secret` and `intended_for` are stored in columns of at most 320 characters.

## rmap-initiate
 
**Description**  
This endpoint receives GPG encrypted messages conforming to RMAP message 1.
 
**Path**
`POST /api/rmap-initiate`


**Parameters**
```json
{
    "payload": <ASCII_armored_base64>
}
```

should decrypt to:

```json
{
    "nonceClient": <u64>,
    "identity": <string>
}
```



**Return**
```json
{
    "payload": <ASCII_armored_base64>
}
```
should decrypt to:

```json
{
    "nonceClient": <u64>,
    "nonceServer": <u64>
}
```

**Specification**
 * The server SHOULD only respond to known identities.
 * All submitted group public keys MUST constitute valid identities.
 * The payload is a gpg encrypted JSON presented as ASCII armored base64, without any GPG headers.
 * The endpoint does not require a bearer token; the client is authenticated by the RMAP handshake itself.
 
## rmap-get-link
 
**Description**  
This endpoint receives GPG encrypted messages conforming to RMAP message 2.
 
**Path**
`POST /api/rmap-get-link`


**Parameters**
```json
{
    "payload": <ASCII_armored_base64>
}
```

should decrypt to:

```json
{
    "nonceServer": <u64>
}
```



**Return**
```json
{
    "payload": <ASCII_armored_base64>
}
```
should decrypt to:

```json
{
    "result":"<32-hex NonceClient||NonceServer>"
}
```

**Specification**
 * `get-version/<result>` SHOULD point to a watermarked version of a PDF specific to the group authenticated by the public key of the client.
 * The watermarked version MUST be created and recorded in the database before the link is returned.
 * The payload is a gpg encrypted JSON presented as ASCII armored base64, without any GPG headers.

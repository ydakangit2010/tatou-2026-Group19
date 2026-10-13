# Incident Journal

## 2026-09-16 – flag_2 captured

### What happened
Group 19 was informed by the teacher that flag_2 had been captured by another group.

### Investigation
During the investigation, we found that the server startup logs were exposing sensitive information.

We also found unsafe shell command handling in one of the watermarking methods. Because the method handled user-controlled input, this could potentially be abused inside the application container.

We could not confirm that this was the exact method used by the attacking group, but it was an important security issue.

### Actions taken
- Replaced flag_2 with the new value provided by the teacher.
- Removed sensitive information from the startup logs.
- Replaced the unsafe shell-based watermarking code with normal Python processing.
- Rebuilt the Tatou service.
- Verified that the health endpoint was working.
- Ran the watermarking tests successfully.

### Result
The identified problems were fixed and the service continued to work normally.




## 2026-09-18 – Follow-up investigation of flag_2 capture

### What happened
After the previous flag_2 incident, we continued reviewing the Tatou server for possible security problems.

### Investigation
We found a security issue in the plugin-loading functionality that could allow unsafe access inside the application container.

We could not confirm whether this was the exact method used by the attacking group, but the issue was serious enough to fix.

### Actions taken
- Added additional validation around plugin handling.
- Disabled the plugin-loading endpoint because it was not required.
- Rebuilt and restarted the server.
- Verified that the endpoint is no longer available.
- Ran the automated tests successfully.
- Pushed the security changes to the main branch.

### Result
The identified plugin-loading issue was fixed and the service continued to work normally.


## 2026-09-20 – Additional container hardening

### What happened
During a follow-up security review, we checked the container setup, exposed services, and how sensitive files were protected.

### Investigation
We confirmed that:

- MariaDB was not exposed externally.
- phpMyAdmin was only available on localhost.
- the Tatou web service was exposed on its expected application port.
- the application container was still running with root privileges.
- some sensitive files inside the container had permissions that were broader than necessary.

### Actions taken
- Reviewed the Docker Compose configuration and removed an obsolete setting.
- Restricted permissions on sensitive files inside the application container.
- Kept internal services such as the database and phpMyAdmin from being publicly exposed.
- Rebuilt and restarted the containers.
- Verified that the Tatou health check still worked correctly.
- Committed and pushed the hardening changes to the main branch.

### Result
The container configuration was improved and sensitive files received more restrictive access controls.

The application was still running as root at this stage, so reducing the privileges of the application process was identified as the next hardening step.



## 2026-09-20 – Third flag_2 capture

### What happened
The teacher informed Group 19 that our flag_2 had been captured again by another group.

### Investigation
We checked the security fixes that had already been added and continued reviewing the container configuration.

We found that the application was still running with more privileges than necessary. We could not confirm exactly how the other group captured the flag, but this was an important security weakness.

### Actions taken
- Replaced flag_2 with the new value provided by the teacher.
- Changed the Tatou application to run as a non-root user.
- Kept sensitive files protected from the application user.
- Verified that uploads and RMAP still work.
- Verified that the disabled plugin endpoint remains blocked.
- Ran the tests successfully.
- Checked that the health endpoint still works.

### Result
The Tatou application now runs with reduced privileges, which limits the impact of future application vulnerabilities.



## 2026-09-20 – Offensive flag capture

As part of the Phase I offensive task, Group 19 tested other Tatou instances in the SOFTSEC lab environment.

We successfully captured Flag 2 from two other groups.

The issue was related to unsafe plugin loading and deserialization, which allowed access to information inside the application container.

The actual flag values and detailed attack steps are not stored in this repository.

Both captured flags were reported to the teacher using the required subject

This exercise also helped us identify security improvements that we applied to our own Tatou server.


## 2026-09-24 – Access-control regression test

### What happened
We reviewed the document deletion endpoint to check that one user could not delete another user's document.

### Actions taken
- Added an automated test where a non-owner tries to delete a document.
- Checked that the server returns HTTP 404 with a document-not-found error.
- Used a fake database to simulate document ownership.

### Result
The test passed and gave us a way to check that unauthorized deletion remains blocked.

## 2026-09-29 – Access-control testing improvements

### What happened
We improved our tests for document ownership. During this work, we also found that `list-versions` used login names instead of numeric user IDs for ownership checks.

### Actions taken
- Added tests covering eight document-related API endpoints.
- Used fake database tests and some MariaDB integration tests.
- Fixed the `list-versions` ownership check to use the user ID.
- Updated file storage to use numeric user IDs instead of login names.
- Added a positive-control test to check that the document owner can still delete their document.

### Result
The new tests gave us better coverage of document access. They also helped us find and fix an ownership problem.

## 2026-09-30 – Document deletion state verification

### What happened
We wanted to check whether the document was actually protected after an unauthorized deletion request, instead of only checking the HTTP response.

### Actions taken
- Added a test to check that a non-owner receives HTTP 404 and the document remains available.
- Checked that the owner can still retrieve the document after the failed deletion.
- Added another test to check that an authorized deletion removes the document and its temporary file.

### Result
The tests passed. They showed that unauthorized deletion did not change the simulated document state, while authorized deletion removed it.

These tests used a fake database and temporary file storage, not the production database.



## 2026-10-11 - Fuzzing and input-validation fixes

### What happened

We used Hypothesis to test the create-watermark API with
different JSON input values.

We found two problems:
- An invalid intended_for value caused a TypeError.
- An invalid position value was accepted instead of being rejected.

### Actions taken

- Added type checks for intended_for and position.
- Added three Hypothesis fuzzing tests.
- Used a fake database and temporary files for safety.
- Ran the fuzzing tests and selected existing tests again.

### Result

All 3 fuzzing tests and 17 existing tests passed.

The fixes were tested in the working source code.
They were not verified on the deployed server.
```


## 2026-10-13 – Flag 2 captured again

### What happened

The teacher informed us that our Flag 2 had been captured again and provided a new value.

### Investigation

We reviewed the current server configuration and the previous security fixes.

We checked application privileges, sensitive file protection, file-related API routes, RMAP, and the previously disabled plugin functionality.

We could not confirm the exact method used to capture the flag.

### Actions taken

- Rotated Flag 2.
- Improved the way Flag 2 is protected inside the server.
- Reduced unnecessary exposure of the flag during application startup.
- Rebuilt and restarted the service.
- Verified that the application still works correctly.
- Ran the automated tests successfully: 46 passed, 17 skipped.
- Checked that the RMAP endpoints still respond correctly.

### Result

Additional protection was added for Flag 2 while keeping the required Tatou functionality working.

The exact capture method could not be confirmed.

# Incident Journal

## 2026-09-16 – flag_2 captured

### What happened
Group 19 was informed by the teacher that flag_2 had been captured by another group.

### Investigation
During the investigation, we found that the server startup logs were printing the actual value of FLAG_2.

We also found a possible command injection vulnerability in the bash-bridge-eof watermarking method. The secret value from the API request was passed into a shell command using subprocess.run(..., shell=True). Since this code runs inside the application container, it could potentially allow an attacker to execute commands inside the container and access files such as `/app/flag`.

We cannot confirm which exact method was used by the attacking group, but this vulnerability was considered a likely cause of the compromise.

### Actions taken
- Rotated flag_2 using the new value provided by the teacher.
- Removed the actual FLAG_2 value from the server startup logs.
- Replaced the shell-based implementation in bash-bridge-eof with Python byte operations.
- Rebuilt the Tatou service.
- Verified that the healthz endpoint was working.
- Ran the watermarking tests successfully.

### Result
The service was restored successfully and the identified vulnerabilities were fixed.




## 2026-09-18 – Follow-up investigation of flag_2 capture

### What happened
After the previous flag_2 incident, we continued checking the server to understand how another group might have been able to access the flag.

### Investigation
While reviewing server.py, we found a security problem in the /api/load-plugin endpoint.

The endpoint allowed an authenticated user to provide a filename for a plugin. The path was not properly checked, so it could potentially allow access to files outside the intended plugin folder.

We also found that the endpoint used Python pickle/dill to load .pkl files. This is risky because a malicious pickle file can execute Python code when it is loaded.

We also checked the running container and found that:

- the server container was running as root;
- flag_2 is stored inside the container at app/flag;
- the flag file could be read by processes running inside the container;
- pkl files existed in the shared storage.

Because of this, the plugin-loading functionality could potentially give an attacker a way to execute code inside the container and access flag_2.

We cannot confirm that this was the exact method used by the other group, but it was a serious security issue and needed to be fixed.

### Actions taken
- Added a check so plugin file paths cannot escape the intended plugin directory.
- Disabled the /api/load-plugin endpoint because it was not needed and unsafe pickle loading could lead to code execution.
- Rebuilt and restarted the server container.
- Checked that the /healthz endpoint was working and the database connection was healthy.
- Tested /api/load-plugin with a valid logged-in user and confirmed that it now returns HTTP 403 with plugin loading is disabled.
- Ran the existing automated tests successfully (7 passed).
- Pushed the security fixes to the main branch.

### Result
The plugin-loading security issue has been fixed. The replacement flag_2 provided by the teacher is still in use.

If flag_2 is captured again, we will continue investigating other possible ways to access the server container.



## 2026-09-20 – Additional container hardening

### What happened
During a follow-up security review, we checked which services were exposed on the VM and how sensitive files were protected inside the server container.

### Investigation
We confirmed that:
- MariaDB is not exposed externally.
- phpMyAdmin is only bound to localhost.
- the Tatou server is exposed on port 5000 as expected.
- the server container still runs as root.
- /app/flag was readable by other users inside the container, while the RMAP private key already had restricted permissions.

### Actions taken
- Removed the obsolete Docker Compose version field.
- Added chmod 600 /app/flag after Flag 2 is initialized by the entrypoint script.
- Rebuilt and restarted the server container.
- Confirmed that /app/flag now has owner-only read/write permissions.
- Verified that the Tatou health check still works.
- Committed, pushed, and merged the hardening change into main.

### Result
The Flag 2 file is now better protected inside the container. The container still runs as root, so moving the application to a non-root user remains a possible future hardening improvement.



## 2026-09-20 – Third flag_2 capture

### What happened
The teacher informed Group 19 that our flag_2 had been captured again by another group.

### Investigation
We checked the security fixes that were already added earlier.

- /api/load-plugin is still disabled.
- The old bash-bridge-eof command injection is still fixed.
- No shell=True was found in the running application code.
- The document queries use parameterized SQL.
- We found that the Tatou server was still running as root inside the container.

We cannot confirm exactly how the other group captured the flag, but running the server as root was still a security risk. If an attacker found another code execution vulnerability, they could potentially read /app/flag.

### Actions taken
- Replaced flag_2 with the new value provided by the teacher.
- Created a separate non-root user for the Tatou application.
- Changed Gunicorn so it now runs as the non-root user instead of root.
- Kept /app/flag owned by root with permission 600.
- Gave the application user permission to write to /app/storage.
- Verified that the application user cannot read /app/flag.
- Verified that uploads still work.
- Verified that the RMAP files are still accessible.
- Verified that /api/load-plugin still returns HTTP 403.
- Ran the tests successfully.
- Checked that /healthz still works.

### Result
The Tatou server is now running as a non-root user. This reduces the risk that a future application vulnerability can be used to read /app/flag.

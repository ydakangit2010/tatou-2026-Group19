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

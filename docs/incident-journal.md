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

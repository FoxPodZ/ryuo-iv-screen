<!-- SPDX-License-Identifier: GPL-3.0-or-later -->

# Local and remote access

The default TCP listener is `127.0.0.1:8746`. Local programs can control the screen without a password. The Unix socket `/run/ryuo-screen/control.sock` grants the same API to its owner and group. Host validation and same-origin checks also cover local requests. JSON content types on mutations and a dedicated binary upload type reject simple cross-site form submissions.

## Serve a password-protected UI over HTTPS

1. Put a TLS reverse proxy in front of the loopback listener. Restrict the backend to the proxy host or a private service network if it must bind a LAN address.
2. Generate the salted scrypt verifier locally. The prompt hides the password and keeps it out of the command line:

   ```sh
   /opt/ryuo-screen/venv/bin/python -c 'from getpass import getpass; from ryuo_screen.auth import PasswordVerifier; print(PasswordVerifier.hash(getpass("Ryuo password: ")))'
   ```

3. Edit `/etc/ryuo-screen/config.toml` using `sudoedit`. Keep the existing top-level options before `[security]`. For a same-host proxy:

   ```toml
   listen_host = "127.0.0.1"
   listen_port = 8746
   lan_enabled = true

   [security]
   password_verifier = "<paste the complete scrypt verifier>"
   trusted_proxy = "127.0.0.1/32"
   ```

4. Set the proxy to **overwrite** forwarded headers with its own verified peer information. Preserve the public request host including a nondefault port. Example nginx directives inside the HTTPS virtual host for `ryuo.example.net`:

   ```nginx
   location / {
       proxy_pass http://127.0.0.1:8746;
       proxy_set_header Host ryuo.example.net;
       proxy_set_header X-Forwarded-Host ryuo.example.net;
       proxy_set_header X-Forwarded-Proto https;
       proxy_set_header X-Forwarded-For $remote_addr;
       proxy_set_header Forwarded "";
       proxy_buffering off;
       proxy_read_timeout 90s;
   }
   ```

   Configure the server certificate, key and allowed hostname in that virtual host. Configure the proxy body limit and upload timeouts to accommodate the files you intend to accept (the application caps uploads at 256 MiB). For a proxy on another host, bind a specific private address, set `trusted_proxy` to that peer's precise CIDR, and restrict the backend port to that peer.

5. Restart `ryuo-screen.service`. From a **remote browser**, open the HTTPS URL and verify that login is required. `GET /api/v1/auth/status` before login should report `required:true` and `authenticated:false`. Missing client forwarding on a loopback proxy can classify the connection as a trusted local client. Only apply trusted-loopback settings on machines where local processes are trusted.

A non-loopback bind requires `lan_enabled = true` and a valid verifier or trusted proxy. Installing only a proxy CIDR delegates **all remote authentication** to the proxy. Protect the entire site at that proxy and limit direct backend access. Plain HTTP exposes credentials and cookies to observers on the network.

## Sessions and CSRF

A successful remote login rotates the session. The browser receives an expiring HttpOnly, SameSite=Strict cookie, marked Secure on HTTPS. The UI reads a separate CSRF token from the login/status JSON and sends `X-CSRF-Token` on session-authenticated POST, PATCH and DELETE requests. Logout revokes the session. Service restart clears sessions.

The server checks the Host and any supplied Origin before mutations, rejects duplicate or ambiguous security headers, and only accepts supported forwarding headers from trusted peers. A proxy must replace client-supplied forwarding values. Check the auth status response and `GET /api/v1/diagnostics` when investigating a login loop.

## Device and data boundary

The service account owns the state, profiles and cache. Its Unix socket and raw-device group are for trusted local operators. Media actions use validated catalog names and generated destination names. Only ADB transfers media bytes to the cooler. Web routes expose named operations, with no arbitrary ADB shell, raw HID resource or firmware update interface.

Share the sanitized diagnostics from Settings. The operational media listing includes the selected ADB serial, and the system config contains the verifier. Limit access to both and to the install backups. [Deployment and SELinux](deployment.md) · [API reference](api.md)

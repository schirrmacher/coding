# Application installation

Application installation is independent of sandbox launchers and host policy:

```sh
make install-apps                         # Pinned Craft releases and icons
applications/install brave               # Empty isolated profile; Downloads default
applications/install uv                  # Preserve the installed binary for wrappers
applications/install vscode              # Seed separate settings and extensions once
applications/install zed                 # Icon and telemetry settings
applications/install orca                # Icon from an installed AppImage
applications/install sigrid              # Expose an already-installed SIGRID package
applications/install codex --source /path/to/standalone-release
```

Run these commands as your normal user. Each installer supports `--help`.
Install Brave Browser through the host package manager first. Its setup command
creates `~/Downloads`, `~/dev`, and a separate browser profile; it does not import
cookies or sessions. Existing download preferences are preserved.

Codex accepts an explicit verified standalone release directory. Its installer
has no dependency on another application's private runtime. Existing independent
releases and original launcher backups are preserved.

`python3 applications/update.py --download-only` verifies releases described by
the existing `.app-updates` manifests. Omit the flag to install those releases.
Downloaded binaries and manifests stay in that cache; updating applications does
not reinstall sandbox wrappers or reload policy.

Run `make test` for both application and sandbox checks. Installer tests cover
repeatability, preservation of existing state, failed copies, release validation,
and harmless help commands.

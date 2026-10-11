# Prepare runtimes through the same user-level entrypoint as host setup.
prepare_installation() {
	python3 "$SANDBOX_ROOT/lib/prepare_runtime.py" <<< "$CONFIG_JSON" || return 1
	mkdir -p "$BIN_DIR" "$DESKTOP_DIR"
}

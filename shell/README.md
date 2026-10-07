# EReader Shell

The shell is intentionally a thin state/navigation layer. Its host development
entry point is `python -m shell.ereader_shell.app`; the device display backend
is not asserted until the J2 Core graphics path has been proven.

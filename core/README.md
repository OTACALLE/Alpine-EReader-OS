# Core

Core is device-independent. The Python reference services provide a testable
policy layer and are packaged into the development rootfs; an Alpine target
package may replace the implementation language only while preserving these
interfaces and tests. OpenRC definitions are included, but are not enabled or
executed on the Windows host.

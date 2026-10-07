# KOReader integration boundary

KOReader remains a separate executable. The shell launches it with exactly one
book path and never links against its Lua runtime or reader libraries. The
launcher expects `/usr/bin/koreader` in a target image. No KOReader fork or
patch is carried by this repository.

The host launcher returns a clear nonzero status if KOReader is absent; that is
intentional and prevents a development stub from being mistaken for rendering.

"""Static file storage used by WhiteNoise.

Manifest (hashed-URL) storage requires a manifest produced by
``collectstatic``. Automated tests force ``DEBUG = False``, which
activates this storage even when no manifest exists, and any template
using ``{% static %}`` would then fail with
``Missing staticfiles manifest entry`` or
``The file '...' could not be found``. Here such failures fall back to
the plain (unhashed) URL instead of raising; in production, where
``collectstatic`` runs at build time, files present in the manifest
still resolve to hashed URLs.
"""

from urllib.parse import urldefrag

from whitenoise.storage import CompressedManifestStaticFilesStorage


class LenientManifestStaticFilesStorage(CompressedManifestStaticFilesStorage):
    manifest_strict = False

    def url(self, name, force=False):
        try:
            return super().url(name, force)
        except ValueError:
            # No manifest entry / no collected file: serve the plain URL.
            return urldefrag(name)[0]

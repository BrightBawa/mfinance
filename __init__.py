import os

# Proxy package: include the original package directory so imports like
# `bi_app.microfinance` resolve to the existing code under
# `apps/bestinvest_app/bestinvest_app` without moving files immediately.
_here = os.path.abspath(os.path.dirname(__file__))
_old_pkg = os.path.abspath(os.path.join(_here, '..', '..', 'bestinvest_app', 'bestinvest_app'))
if os.path.isdir(_old_pkg) and _old_pkg not in __path__:
    __path__.insert(0, _old_pkg)

__version__ = "0.0.1"

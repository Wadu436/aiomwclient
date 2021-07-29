# aiomwclient

aiomwclient is an asynchronous Python client library for the
[MediaWiki API](https://mediawiki.org/wiki/API) based on [mwclient](https://github.com/mwclient/mwclient). The goal is to provide a similar amount of access as mwclient.
It works with Python 3.5 and above, and supports MediaWiki 1.16 and above.
For functions not available in the current MediaWiki, a `MediaWikiVersionError` is raised.

The current [development version](https://github.com/mwclient/mwclient)
can be installed from GitHub:

```
$ pip install git+git://github.com/Wadu436/aiomwclient.git
```

## Documentation

There isn't documentation specific to this project yet, however most of the interface is the same as mwclient's, but asynchronous. You can find mwclient's documentation as [Read the Docs](http://mwclient.readthedocs.io/en/latest/).

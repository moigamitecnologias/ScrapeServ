# Client

This client is made as a reference implementation in Python for how your app might parse a response from the API.

You should send an HTTP request and parse the multipart/mixed response (see the [standard](https://www.w3.org/Protocols/rfc1341/7_2_Multipart.html)). The parts are as described in the project README.

In Python, you can use requests_toolbelt (an extension of the requests library, written by the same authors).

Be sure to install `requests_toolbelt` like:

```
python3 -m pip install requests_toolbelt
```

And run the client like:

```
python3 client.py https://us.ai
```

If you'd prefer to use a library rather than copy this implementation, please create a GitHub issue. PRs welcome.
